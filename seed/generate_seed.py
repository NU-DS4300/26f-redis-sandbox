#!/usr/bin/env python3
"""Generate seed.redis: sample data for "ShopStream", a fictional e-commerce web service.

Deterministic (fixed RNG seed), stdlib only. Output is a plain list of redis-cli
commands; lines starting with '#' are comments stripped by load.sh.

    python3 seed/generate_seed.py > seed/seed.redis
"""

import json
import random
from datetime import datetime, timedelta, timezone

rng = random.Random(4300)
out: list[str] = []

SAFE = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:._-/@$+*=?,")


def q(value) -> str:
    """Quote one argument the way redis-cli's argument parser expects."""
    s = str(value)
    if s and set(s) <= SAFE:
        return s
    if "'" not in s and "\\" not in s:
        return f"'{s}'"
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def cmd(*args) -> None:
    out.append(" ".join(q(a) for a in args))


def section(title: str) -> None:
    out.append("")
    out.append(f"# --- {title} ---")


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


NOW = datetime(2026, 10, 5, 14, 0, 0, tzinfo=timezone.utc)
DAYS = [(NOW - timedelta(days=d)).date() for d in range(6, -1, -1)]  # 7 days, oldest first

# --------------------------------------------------------------------------- users
FIRST = ["Ava", "Liam", "Maya", "Noah", "Zoe", "Ethan", "Priya", "Lucas", "Chloe", "Mateo",
         "Aisha", "Owen", "Sofia", "Kai", "Nora", "Ravi", "Elena", "Jonah", "Mei", "Diego"]
LAST = ["Nguyen", "Smith", "Patel", "Garcia", "Kim", "Johnson", "Chen", "Lopez", "Brown",
        "Okafor", "Rossi", "Murphy", "Silva", "Cohen", "Haddad"]
CITIES = [("Boston", "MA"), ("New York", "NY"), ("Chicago", "IL"), ("Austin", "TX"),
          ("Seattle", "WA"), ("Denver", "CO"), ("Atlanta", "GA"), ("San Jose", "CA"),
          ("Portland", "ME"), ("Miami", "FL")]
PLANS = ["free"] * 6 + ["premium"] * 3 + ["student"]

USER_IDS = list(range(1, 101))
users = {}
for uid in USER_IDS:
    first, last = rng.choice(FIRST), rng.choice(LAST)
    city, state = rng.choice(CITIES)
    users[uid] = {
        "name": f"{first} {last}",
        "email": f"{first.lower()}.{last.lower()}{uid}@example.com",
        "city": city,
        "state": state,
        "plan": rng.choice(PLANS),
        "signup_date": (NOW - timedelta(days=rng.randint(10, 900))).date().isoformat(),
    }

# ------------------------------------------------------------------------ products
CATALOG = {
    "electronics": [("Wireless Earbuds", 79.99), ("USB-C Hub 7-in-1", 39.99), ("Mechanical Keyboard", 119.00),
                    ("27in 4K Monitor", 329.99), ("Portable SSD 1TB", 99.99), ("Noise-Cancelling Headphones", 249.00),
                    ("Smart Watch", 199.99), ("Webcam 1080p", 59.99), ("Bluetooth Speaker", 49.99),
                    ("Laptop Stand", 34.99)],
    "books": [("Designing Data-Intensive Applications", 44.99), ("Redis in Action", 39.99),
              ("Database Internals", 49.99), ("The Pragmatic Programmer", 42.00), ("Python for Data Analysis", 54.99),
              ("Clean Code", 37.99), ("Streaming Systems", 46.50), ("Fundamentals of Data Engineering", 59.99),
              ("Grokking Algorithms", 34.99), ("SQL Performance Explained", 29.99)],
    "home": [("Pour-Over Coffee Kettle", 54.99), ("Cast Iron Skillet", 29.99), ("LED Desk Lamp", 27.49),
             ("Weighted Blanket", 89.00), ("French Press", 24.99), ("Air Purifier", 149.99),
             ("Robot Vacuum", 279.00), ("Ceramic Mug Set", 32.00), ("Electric Toothbrush", 69.99),
             ("Standing Desk Mat", 44.99)],
    "sports": [("Yoga Mat", 25.99), ("Adjustable Dumbbells", 189.00), ("Running Shoes", 129.99),
               ("Insulated Water Bottle", 32.99), ("Resistance Bands", 19.99), ("Foam Roller", 22.49),
               ("Cycling Helmet", 64.99), ("Trail Backpack 30L", 99.00), ("Jump Rope", 12.99),
               ("Fitness Tracker", 89.99)],
    "grocery": [("Cold Brew Coffee 12pk", 29.99), ("Dark Chocolate Bar", 3.99), ("Organic Green Tea", 8.49),
                ("Trail Mix 2lb", 14.99), ("Protein Bars 12ct", 24.99), ("Sparkling Water 24pk", 13.99),
                ("Maple Syrup", 11.99), ("Instant Ramen 10pk", 9.99), ("Olive Oil 1L", 16.99),
                ("Mixed Nuts 1.5lb", 17.49)],
}
BRANDS = ["Acme", "Northwind", "Contoso", "Globex", "Initech", "Umbrella", "Stark", "Wayne"]

products = {}
pid = 1001
for category, items in CATALOG.items():
    for name, price in items:
        products[pid] = {
            "name": name,
            "category": category,
            "brand": rng.choice(BRANDS),
            "price": f"{price:.2f}",
            "stock": rng.randint(0, 500),
            "rating": f"{rng.uniform(3.2, 5.0):.1f}",
            "review_count": rng.randint(3, 4000),
        }
        pid += 1
PRODUCT_IDS = list(products)

# Popularity follows a long tail: a few products get most of the traffic.
popularity = {p: 1 / (rank + 1) ** 0.9 for rank, p in enumerate(rng.sample(PRODUCT_IDS, len(PRODUCT_IDS)))}


def popular_product() -> int:
    return rng.choices(PRODUCT_IDS, weights=[popularity[p] for p in PRODUCT_IDS])[0]


by_popularity = sorted(PRODUCT_IDS, key=lambda p: -popularity[p])

# ------------------------------------------------------------------------- output
out.append("# ShopStream sample data. GENERATED by generate_seed.py -- edit the generator, not this file.")

section("STRING + JSON value: cache-aside API responses (cache:api:<route>), TTL 1h")
for p in by_popularity[:15]:
    body = {"id": p, **products[p], "cached_at": iso(NOW)}
    cmd("SET", f"cache:api:/v1/products/{p}", json.dumps(body, separators=(",", ":")), "EX", 3600)
for category in CATALOG:
    top = [p for p in by_popularity if products[p]["category"] == category][:5]
    body = {"category": category, "top": [{"id": p, "name": products[p]["name"]} for p in top]}
    cmd("SET", f"cache:api:/v1/categories/{category}/top", json.dumps(body, separators=(",", ":")), "EX", 600)

section("STRING counters: product page views (pageviews:product:<id>) -- INCR target")
for p in PRODUCT_IDS:
    cmd("SET", f"pageviews:product:{p}", int(popularity[p] * 50_000) + rng.randint(0, 300))

section("STRING counters with TTL: fixed-window API rate limiting (ratelimit:user:<id>:<hour>)")
window = NOW.strftime("%Y-%m-%dT%H")
for uid in rng.sample(USER_IDS, 10):
    cmd("SET", f"ratelimit:user:{uid}:{window}", rng.randint(1, 120), "EX", 3600)

section("HASH: user profiles (user:<id>)")
for uid, u in users.items():
    cmd("HSET", f"user:{uid}", *[x for kv in u.items() for x in kv])

section("HASH: product catalog (product:<id>)")
for p, prod in products.items():
    cmd("HSET", f"product:{p}", *[x for kv in prod.items() for x in kv])

section("HASH with TTL: login sessions (session:<token>), expire 30 min - 24 h")
AGENTS = ["Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) Safari/605.1.15",
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/140.0",
          "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5) Mobile/15E148",
          "ShopStreamApp/3.2.1 (Android 15)"]
for uid in rng.sample(USER_IDS, 25):
    token = "%032x" % rng.getrandbits(128)
    created = NOW - timedelta(minutes=rng.randint(5, 600))
    cmd("HSET", f"session:{token}",
        "user_id", uid,
        "created_at", iso(created),
        "last_seen", iso(created + timedelta(minutes=rng.randint(0, 5))),
        "ip", f"10.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}",
        "user_agent", rng.choice(AGENTS))
    cmd("EXPIRE", f"session:{token}", rng.choice([1800, 3600, 7200, 43200, 86400]))

section("HASH with TTL: shopping carts (cart:<user_id>) field=product_id value=qty, expire 7 days")
for uid in rng.sample(USER_IDS, 15):
    items = rng.sample(PRODUCT_IDS, rng.randint(1, 4))
    cmd("HSET", f"cart:{uid}", *[x for p in items for x in (p, rng.randint(1, 3))])
    cmd("EXPIRE", f"cart:{uid}", 7 * 86400)

section("LIST: recently viewed products per user (recent:<user_id>), newest first, capped at 10")
for uid in rng.sample(USER_IDS, 20):
    viewed = list(dict.fromkeys(popular_product() for _ in range(25)))[:10]
    cmd("RPUSH", f"recent:{uid}", *viewed)

section("LIST: background job queue (queue:emails) -- producers LPUSH, workers RPOP/BRPOP")
for i, uid in enumerate(rng.sample(USER_IDS, 6)):
    job = {"job_id": f"job-{9000 + i}", "type": rng.choice(["order_confirmation", "shipping_update", "password_reset"]),
           "to": users[uid]["email"], "enqueued_at": iso(NOW - timedelta(seconds=30 * (6 - i)))}
    cmd("LPUSH", "queue:emails", json.dumps(job, separators=(",", ":")))

section("SET: products per category (category:<name>) and merchandising tags (tag:<name>)")
for category in CATALOG:
    cmd("SADD", f"category:{category}", *[p for p in PRODUCT_IDS if products[p]["category"] == category])
for tag, share in [("on_sale", 0.3), ("new_arrival", 0.2), ("free_shipping", 0.5)]:
    cmd("SADD", f"tag:{tag}", *sorted(rng.sample(PRODUCT_IDS, int(len(PRODUCT_IDS) * share))))

section("SORTED SET: leaderboards (leaderboard:*) member=product_id")
cmd("ZADD", "leaderboard:bestsellers:2026-10",
    *[x for p in PRODUCT_IDS for x in (int(popularity[p] * 900) + rng.randint(0, 25), p)])
cmd("ZADD", "leaderboard:top_rated", *[x for p in PRODUCT_IDS for x in (products[p]["rating"], p)])

section("HYPERLOGLOG: approximate unique visitors per day (uniques:<date>)")
visitor_pool = [f"v{n:05d}" for n in range(6000)]
regulars = visitor_pool[:700]  # return every day -> overlap makes PFMERGE interesting
for day in DAYS:
    todays = set(rng.sample(regulars, rng.randint(400, 650)))
    todays |= set(rng.sample(visitor_pool[700:], rng.randint(600, 1800)))
    todays = sorted(todays)
    for i in range(0, len(todays), 250):
        cmd("PFADD", f"uniques:{day.isoformat()}", *todays[i:i + 250])

section("STREAM: clickstream events (events:clickstream), entry ID = event time in ms")
t = NOW - timedelta(hours=2)
for _ in range(400):
    t += timedelta(milliseconds=rng.randint(200, 35_000))
    event = rng.choices(["page_view", "search", "add_to_cart", "remove_from_cart", "checkout", "purchase"],
                        weights=[60, 12, 12, 3, 7, 6])[0]
    fields = ["user_id", rng.choice(USER_IDS), "event", event]
    if event == "search":
        fields += ["query", rng.choice(["redis book", "headphones", "coffee", "yoga", "monitor", "ssd", "protein"])]
    else:
        fields += ["product_id", popular_product()]
    cmd("XADD", "events:clickstream", f"{int(t.timestamp() * 1000)}-0", *fields)

section("JSON (Redis 8 built-in): order documents with nested line items (order:<id>)")
STATUSES = ["placed", "paid", "shipped", "shipped", "delivered", "delivered", "delivered", "cancelled"]
for oid in range(5001, 5031):
    uid = rng.choice(USER_IDS)
    lines = []
    for p in rng.sample(PRODUCT_IDS, rng.randint(1, 4)):
        qty = rng.randint(1, 3)
        lines.append({"product_id": p, "name": products[p]["name"], "qty": qty, "unit_price": float(products[p]["price"])})
    order = {
        "order_id": oid,
        "user_id": uid,
        "status": rng.choice(STATUSES),
        "placed_at": iso(NOW - timedelta(hours=rng.randint(1, 240))),
        "shipping": {"city": users[uid]["city"], "state": users[uid]["state"]},
        "items": lines,
        "total": round(sum(line["qty"] * line["unit_price"] for line in lines), 2),
    }
    cmd("JSON.SET", f"order:{oid}", "$", json.dumps(order, separators=(",", ":")))

section("GEO: fulfillment centers (geo:warehouses) as longitude latitude member")
for lon, lat, code in [(-71.0589, 42.3601, "BOS1"), (-74.1724, 40.7357, "EWR2"), (-84.3880, 33.7490, "ATL1"),
                       (-87.6298, 41.8781, "ORD3"), (-96.7970, 32.7767, "DFW1"), (-119.8138, 39.5296, "RNO1"),
                       (-122.3321, 47.6062, "SEA4")]:
    cmd("GEOADD", "geo:warehouses", lon, lat, code)

print("\n".join(out))
