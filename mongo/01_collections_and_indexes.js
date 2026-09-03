db = db.getSiblingDB('ridesync');

db.createCollection("TelemetryPings", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["vehicle_id", "location", "is_available", "created_at"],
      properties: {
        vehicle_id: { bsonType: "string" },
        location: {
          bsonType: "object",
          required: ["type", "coordinates"],
          properties: {
            type: { enum: ["Point"] },
            coordinates: {
              bsonType: "array",
              minItems: 2,
              maxItems: 2,
              items: { bsonType: "double" }
            }
          }
        },
        is_available: { bsonType: "bool" },
        created_at: { bsonType: "date" }
      }
    }
  }
});

db.createCollection("TripReviews", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["trip_id", "rating", "tags", "created_at"],
      properties: {
        trip_id: { bsonType: "string" },
        rating: { bsonType: "int", minimum: 1, maximum: 5 },
        tags: { bsonType: "array", items: { bsonType: "string" } },
        created_at: { bsonType: "date" }
      }
    }
  }
});


db.createCollection("VehicleMetadata");


db.TelemetryPings.createIndex({ location: "2dsphere" });


db.TelemetryPings.createIndex({ created_at: 1 }, { expireAfterSeconds: 7200 });

db.TripReviews.createIndex({ rating: 1 });

