db.TripReviews.aggregate([
  {
    $match: {
      rating: { $gte: 1 }
    }
  },
  {
    $facet: {
      rating_distribution: [
        { $group: { _id: "$rating", count: { $sum: 1 } } },
        { $sort: { _id: 1 } }
      ],
      driver_feedback_tags: [
        { $unwind: "$tags" },
        { $group: { _id: "$tags", count: { $sum: 1 } } },
        { $sort: { count: -1 } }
      ],
      overall_average: [
        { $group: { _id: null, avg_rating: { $avg: "$rating" } } }
      ]
    }
  }
]);