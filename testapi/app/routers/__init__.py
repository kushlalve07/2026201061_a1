from app.routers import analytics, bookings, health, map, reviews, riders, trips, vehicles

ALL_ROUTERS = [
    health.router,
    riders.router,
    vehicles.router,
    trips.router,
    bookings.router,
    analytics.router,
    map.router,
    reviews.router,
]
