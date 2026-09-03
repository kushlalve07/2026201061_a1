db.TripReviews.aggregate([
  {
    $facet: {
      "rating_distribution": [
        { 
          $group: { 
            _id: "$rating", 
            count: { $sum: 1 } 
          } 
        },
        { $sort: { _id: 1 } }
      ],


      "top_feedback_tags": [
        { $unwind: "$tags" },
        { 
          $group: { 
            _id: "$tags", 
            count: { $sum: 1 } 
          } 
        },
        { $sort: { count: -1 } },
        { $limit: 5 }
      ],

      "overall_summary": [
        { 
          $group: { 
            _id: null, 
            avg_rating: { $avg: "$rating" },
            total_reviews: { $sum: 1 }
          } 
        },
        {
          $project: {
            _id: 0,
            avg_rating: { $round: ["$avg_rating", 2] },
            total_reviews: 1
          }
        }
      ]
    }
  }
]);