db = db.getSiblingDB('ridesync');

db.createCollection('VehicleMetadata');
db.createCollection('TripReviews');
db.createCollection('TelemetryPings');