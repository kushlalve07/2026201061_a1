db.TelemetryPings.aggregate([
  {
    $geoNear: {
      near: { 
        type: "Point", 
        coordinates: [-122.4194, 37.7749] 
      },
      distanceField: "distance_meters",
      maxDistance: 5000, 
      query: { is_available: true }, spherical: true
    }
  },
  {
    $project: {
      _id: 0,
      vehicle_id: 1,
      distance_meters: { $round: ["$distance_meters", 2] },
      location: 1,
      created_at: 1
    }
  },
  { $limit: 1 }
]);