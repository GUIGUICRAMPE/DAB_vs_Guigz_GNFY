from geopy.distance import geodesic

# Test simple :
print(geodesic((48.8566, 2.3522), (45.7640, 4.8357)).km)  # Paris -> Lyon
