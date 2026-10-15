# DS4300 — Redis + Redis Insight Sandbox
- add more notes later
A local Redis 8 server, the Redis Insight GUI, and sample data for **ShopStream**, a made-up
e-commerce web service. The data shows the things Redis usually does in front of a big data
backend: caching API responses, sessions, counters, rate limits, leaderboards, approximate
unique counts, and event streams.

## Start

Requires Docker Desktop (or Docker Engine + Compose v2).

```bash
docker compose up -d
```

| Service        | URL / port               | Notes                                                    |
|----------------|--------------------------|----------------------------------------------------------|
| `redis`        | `localhost:6379`         | Redis 8 with JSON, Search, etc. built in. Data persists in a Docker volume (AOF). |
| `redisinsight` | <http://localhost:5540>  | The connection **DS4300 ShopStream** is already set up.  |
| `seed`         | one-shot                 | Loads `seed/seed.redis` if Redis is empty, then exits.   |

Command line access (no local install needed):

```bash
docker exec -it ds4300-redis redis-cli
```

Already running Redis locally on port 6379? Stop it, or change the host port in `docker-compose.yml`.

## The data (340 keys)

Everything belongs to ShopStream. Key names follow the usual Redis convention
`<kind>:<id>`; the colons mean nothing to Redis, but Redis Insight uses them to group keys into
folders. The other keys point back to three main records by id:

| Record   | Ids         | How many | Notes                                                       |
|----------|-------------|----------|-------------------------------------------------------------|
| User     | 1–100       | 100      |                                                             |
| Product  | 1001–1050   | 50       | 10 in each category: `electronics`, `books`, `home`, `sports`, `grocery` |
| Order    | 5001–5030   | 30       |                                                             |

The data's clock is fixed at **2026-10-05 14:00 UTC**: timestamps, dates, and the stream are
all relative to that time.

### Records

| Key                | Type | Count | Contents                                                                 |
|--------------------|------|-------|--------------------------------------------------------------------------|
| `user:<id>`        | Hash | 100   | `name`, `email`, `city`, `state`, `plan` (`free`/`premium`/`student`), `signup_date` |
| `product:<id>`     | Hash | 50    | `name`, `category`, `brand`, `price`, `stock`, `rating`, `review_count`   |
| `order:<id>`       | JSON | 30    | `order_id`, `user_id`, `status`, `placed_at`, `shipping` {`city`, `state`}, `items[]` {`product_id`, `name`, `qty`, `unit_price`}, `total` |

### Web app state (all of these expire)

| Key                                      | Type   | Count | Expires after | Contents                                                   |
|------------------------------------------|--------|-------|---------------|------------------------------------------------------------|
| `cache:api:/v1/products/<id>`            | String | 15    | 1 h           | JSON copy of the product, plus `cached_at`, for the 15 most popular products |
| `cache:api:/v1/categories/<category>/top`| String | 5     | 10 min        | JSON list of the category's top 5 products (`id`, `name`)  |
| `session:<token>`                        | Hash   | 25    | 30 min–24 h   | `user_id`, `created_at`, `last_seen`, `ip`, `user_agent`. Token is 32 hex characters |
| `cart:<user_id>`                         | Hash   | 15    | 7 days        | One field per product: field = product id, value = quantity |
| `ratelimit:user:<user_id>:<hour>`        | String | 10    | 1 h           | Number of API requests in that hour (`<hour>` looks like `2026-10-05T14`) |

### Counters and analytics

| Key                                  | Type        | Count | Contents                                                       |
|--------------------------------------|-------------|-------|----------------------------------------------------------------|
| `pageviews:product:<id>`             | String      | 50    | Integer page view count, one per product                      |
| `leaderboard:bestsellers:2026-10`    | Sorted set  | 1     | Member = product id, score = units sold in October 2026        |
| `leaderboard:top_rated`              | Sorted set  | 1     | Member = product id, score = average rating (3.2–5.0)         |
| `uniques:<date>`                     | HyperLogLog | 7     | Approximate unique visitors per day, 2026-09-29 to 2026-10-05. Many visitors come back every day, so the count across days is less than the sum of the daily counts |
| `events:clickstream`                 | Stream      | 1     | 400 events from the 2 hours before 14:00 UTC. Entry ID = event time in ms. Fields: `user_id`, `event` (`page_view`, `search`, `add_to_cart`, `remove_from_cart`, `checkout`, `purchase`), then `query` for searches or `product_id` for everything else |

### Lists, sets, and locations

| Key                       | Type | Count | Contents                                                              |
|---------------------------|------|-------|-----------------------------------------------------------------------|
| `recent:<user_id>`        | List | 20    | Up to 10 recently viewed product ids, newest first                    |
| `queue:emails`            | List | 1     | 6 JSON email jobs (`job_id`, `type`, `to`, `enqueued_at`). Producers `LPUSH` new jobs, workers `RPOP` them, so the oldest job is on the right |
| `category:<category>`     | Set  | 5     | Product ids in that category                                          |
| `tag:<tag>`               | Set  | 3     | Product ids with that tag: `on_sale`, `new_arrival`, `free_shipping`  |
| `geo:warehouses`          | Geo  | 1     | 7 fulfillment centers: `BOS1`, `EWR2`, `ATL1`, `ORD3`, `DFW1`, `RNO1`, `SEA4` |

### Expiring keys

The keys under "Web app state" **expire on purpose**, so you can watch them with `TTL`. Their
timers start when the data is loaded, not at the fixed 14:00 time. After 10 minutes the
category caches are gone; after an hour the product caches and rate limits are gone too (so
`GET cache:api:/v1/products/1020` below will return nil). Sessions last up to a day and carts
a week. Reload the data any time (see [Reset / reload](#reset--reload)).

## Things to try

```text
SCAN 0 MATCH session:* COUNT 100                  # use SCAN, not KEYS, on real servers
TYPE user:42
HGETALL user:42
HGET product:1020 price
GET cache:api:/v1/products/1020
TTL cache:api:/v1/products/1020
INCR pageviews:product:1020
SET ratelimit:user:42:demo 0 EX 60 NX              # then INCR it a few times and watch TTL
LRANGE recent:11 0 4
LPUSH recent:11 1001                               # then LTRIM recent:11 0 9 to cap it
SINTER category:electronics tag:on_sale            # electronics that are on sale
ZREVRANGE leaderboard:bestsellers:2026-10 0 9 WITHSCORES
ZINCRBY leaderboard:bestsellers:2026-10 50 1001
PFCOUNT uniques:2026-10-05
PFCOUNT uniques:2026-09-29 uniques:2026-10-05      # uniques across both days (not the sum)
XRANGE events:clickstream - + COUNT 5
XREVRANGE events:clickstream + - COUNT 5
JSON.GET order:5001 $.items[*].name
GEOSEARCH geo:warehouses FROMLONLAT -71.09 42.34 BYRADIUS 500 km WITHDIST ASC
```

You can run these in Redis Insight's **Workbench** tab or in `redis-cli`.

## Reset / reload

```bash
docker compose run --rm -e FORCE=1 seed   # wipe Redis and reload the sample data
docker compose down                        # stop; data is kept
docker compose down -v                     # stop and delete all data (next `up` reseeds)
```

## Changing the data

`seed/seed.redis` is generated. Edit `seed/generate_seed.py` (Python 3, standard library only;
output is the same on every run), then:

```bash
python3 seed/generate_seed.py > seed/seed.redis
docker compose run --rm -e FORCE=1 seed
```
