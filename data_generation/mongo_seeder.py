import random
from datetime import datetime, timedelta
from pymongo import MongoClient
from faker import Faker

fake = Faker()

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "ridesync"
BATCH_SIZE = 25000
TOTAL_PINGS = 500000

# Base coordinates center (San Francisco)
CENTER_LAT = 37.7749
CENTER_LNG = -122.4194

def seed_ridesync_mongo():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    
    print("Connected to MongoDB. Generating ridesync dataset...")

    vehicle_ids = [f"VEHICLE_{i:05d}" for i in range(1, 1001)]


    pings_collection = db["TelemetryPings"]
    pings_collection.drop() 

    pings_collection.create_index([("location", "2dsphere")])
    pings_collection.create_index([("created_at", 1)], expireAfterSeconds=7200)

    ping_batch = []

    print(f"Generating {TOTAL_PINGS} TelemetryPings...")
    for i in range(1, TOTAL_PINGS + 1):
        lat = CENTER_LAT + random.uniform(-0.045, 0.045)
        lng = CENTER_LNG + random.uniform(-0.045, 0.045)
        
        ping_doc = {
            "vehicle_id": random.choice(vehicle_ids),
            "location": {
                "type": "Point",
                "coordinates": [lng, lat]
            },
            "is_available": random.choice([True, True, False]), # 66% available
            "speed_kmh": round(random.uniform(0.0, 65.0), 1),
            "created_at": datetime.utcnow() - timedelta(seconds=random.randint(0, 7000))
        }
        ping_batch.append(ping_doc)

        if len(ping_batch) >= BATCH_SIZE:
            pings_collection.insert_many(ping_batch, ordered=False)
            print(f"Inserted {i} / {TOTAL_PINGS} telemetry pings...")
            ping_batch.clear()

    if ping_batch:
        pings_collection.insert_many(ping_batch, ordered=False)


    metadata_collection = db["VehicleMetadata"]
    metadata_collection.drop()
    metadata_collection.create_index([("vehicle_id", 1)], unique=True)

    sample_features = [
        "Leather Seats", "Dashcam", "Pet Friendly", 
        "Child Seat", "WiFi", "Bluetooth", "Sunroof"
    ]

    metadata_docs = []
    print("Generating 1,000 VehicleMetadata records...")
    for v_id in vehicle_ids:
        num_inspections = random.randint(1, 3)
        inspection_records = []
        for _ in range(num_inspections):
            inspection_records.append({
                "passed": random.choice([True, True, True, False]), # 75% pass rate
                "inspected_at": datetime.utcnow() - timedelta(days=random.randint(1, 180)),
                "inspector": fake.name()
            })

        metadata_doc = {
            "vehicle_id": v_id,
            "inspection_records": inspection_records,
            "features": random.sample(sample_features, k=random.randint(1, 4))
        }
        metadata_docs.append(metadata_doc)

    metadata_collection.insert_many(metadata_docs)


    reviews_collection = db["TripReviews"]
    reviews_collection.drop()
    reviews_collection.create_index([("rating", 1)])

    sample_tags = [
        "Smooth Driving", "Clean Vehicle", "Great Music", 
        "Polite Driver", "Fast Route", "Safe Driver", "Cold AC"
    ]

    review_docs = []
    print("Generating 10,000 TripReviews...")
    for _ in range(10000):
        review_doc = {
            "trip_id": fake.uuid4(),
            "rider_id": fake.uuid4(),
            "vehicle_id": random.choice(vehicle_ids),
            "rating": random.choices([1, 2, 3, 4, 5], weights=[5, 5, 10, 30, 50])[0],
            "tags": random.sample(sample_tags, k=random.randint(1, 3)),
            "comment": fake.sentence(),
            "created_at": datetime.utcnow() - timedelta(days=random.randint(0, 30))
        }
        review_docs.append(review_doc)

    reviews_collection.insert_many(review_docs)
    print("MongoDB Seeding Complete!")

if __name__ == "__main__":
    seed_ridesync_mongo()
