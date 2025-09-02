import pandas as pd
import networkx as nx
import requests
import folium
from geopy.geocoders import Nominatim
import time

routes_df = pd.read_csv("routes.csv")
fuel_df = pd.read_csv("ship_fuel_efficiency.csv")
port_df = pd.read_csv("Port_Data.csv")

G = nx.DiGraph()
for _, row in routes_df.iterrows():
    G.add_edge(row["Source"].strip(), row["Destination"].strip(), distance=row["Distance_km"])

geolocator = Nominatim(user_agent="ship_routing")

def get_port_coordinates(port_name):
    try:
        location = geolocator.geocode(port_name, timeout=10)
        time.sleep(1)
        return (location.latitude, location.longitude) if location else None
    except:
        return None

def get_weather(lat, lon):
    api_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,wind_speed_10m"
    try:
        response = requests.get(api_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                "temperature": data["hourly"]["temperature_2m"][:3],
                "wind_speed": data["hourly"]["wind_speed_10m"][:3]
            }
    except:
        pass
    return {"temperature": ["N/A"], "wind_speed": ["N/A"]}

def get_fuel_price():
    headers = {
        "Authorization": "Bearer e21cb358a68ba4815f0f451efabe1da61c1530dff57ea911488686ac61d5ebb7"
    }
    try:
        response = requests.get("https://api.oilpriceapi.com/v1/prices/latest", headers=headers, timeout=5)
        if response.status_code == 200:
            return float(response.json()["data"]["price"])
    except:
        pass
    return 1.5

def get_port_congestion(port_name):
    return 500

def find_best_routes(start_port, end_port):
    try:
        return [nx.dijkstra_path(G, source=start_port, target=end_port, weight="distance")]
    except nx.NetworkXNoPath:
        return None

def calculate_fuel_cost(ship_type, distance_km, fuel_price):
    ship_type_clean = ship_type.strip().lower()
    fuel_data = fuel_df[fuel_df["ship_type"].str.lower().str.strip() == ship_type_clean]
    if fuel_data.empty:
        print(f"⚠️ No fuel data for ship type '{ship_type}'. Using default rate.")
        fuel_consumption = 150
    else:
        fuel_consumption = fuel_data["fuel_consumption"].values[0]
    return round(fuel_consumption * distance_km * fuel_price, 2)

def get_port_halt_cost(port):
    match = port_df[port_df["Port Name"].str.strip() == port]
    if not match.empty:
        return match["Vessels in Port"].values[0] * 10
    return 0

print("== Ship Routing Optimization System ==")

start_port = input("Enter the starting port: ").strip()
end_port = input("Enter the destination port: ").strip()
ship_type = input("Enter the ship type: ").strip()
ship_age = int(input("Enter the ship's age (in years): "))

if start_port not in G.nodes:
    print(f"❌ Start port '{start_port}' not in the route dataset.")
    exit()
if end_port not in G.nodes:
    print(f"❌ Destination port '{end_port}' not in the route dataset.")
    exit()

fuel_price = get_fuel_price()
print(f"\n⛽ Real-Time Fuel Price: ${fuel_price:.2f} per liter")

best_routes = find_best_routes(start_port, end_port)
if not best_routes:
    print("❌ No valid path found.")
    exit()

route_options = []
for route in best_routes:
    total_distance = sum(G[route[i]][route[i+1]]["distance"] for i in range(len(route) - 1))
    fuel_cost = calculate_fuel_cost(ship_type, total_distance, fuel_price)
    halt_cost = sum(get_port_halt_cost(port) for port in route)
    total_cost = fuel_cost + halt_cost
    total_duration = round(total_distance / 20, 2)

    weather_info = {}
    for port in route:
        coords = get_port_coordinates(port)
        if coords:
            weather_info[port] = get_weather(*coords)
        else:
            weather_info[port] = {"temperature": ["N/A"], "wind_speed": ["N/A"]}

    congestion_levels = {port: get_port_congestion(port) for port in route}
    issues, precautions = [], []
    for port in route:
        if congestion_levels[port] > 500:
            issues.append(f"⚠️ Heavy congestion at {port}")
            precautions.append("✅ Adjust schedule or reroute")
        try:
            wind_values = weather_info[port]["wind_speed"]
            if max(wind_values) != "N/A" and max(wind_values) > 30:
                issues.append(f"⚠️ High winds near {port}")
                precautions.append("✅ Reduce speed")
        except:
            continue

    route_options.append({
        "route": route, "distance": total_distance, "duration": total_duration,
        "fuel_cost": fuel_cost, "halt_cost": halt_cost, "total_cost": total_cost,
        "issues": issues, "precautions": precautions, "weather": weather_info
    })

best_route = min(route_options, key=lambda x: x["total_cost"])

for idx, route in enumerate(route_options):
    print(f"\n🚢 Route {idx+1}: {' -> '.join(route['route'])}")
    print(f"📏 Distance: {route['distance']} km")
    print(f"⏳ Duration: {route['duration']} hours")
    print(f"⛽ Fuel Cost: ${route['fuel_cost']}")
    print(f"🏴‍☠️ Halt Charges: ${route['halt_cost']}")
    print(f"💵 **Total Cost: ${route['total_cost']}**")
    print(f"⚠️ Issues: {', '.join(route['issues']) if route['issues'] else 'None'}")
    print(f"✅ Precautions: {', '.join(route['precautions']) if route['precautions'] else 'None'}")

    print("\n🌦️ **Weather Along the Route:**")
    for port, weather in route["weather"].items():
        print(f"📍 {port}: Temperature {weather['temperature']}°C, Wind Speed {weather['wind_speed']} km/h")

print("\n✅ **AI-Optimized Best Route:**")
print(f"🚢 Route: {' -> '.join(best_route['route'])}")
print(f"📏 Distance: {best_route['distance']} km")
print(f"⏳ Duration: {best_route['duration']} hours")
print(f"⛽ Fuel Cost: ${best_route['fuel_cost']}")
print(f"🏴‍☠️ Halt Charges: ${best_route['halt_cost']}")
print(f"💵 **Total Cost: ${best_route['total_cost']}**")
print(f"✅ Selected as the safest & most cost-efficient route")

try:
    ship_map = folium.Map(location=get_port_coordinates(start_port), zoom_start=4)
    for port in best_route["route"]:
        coords = get_port_coordinates(port)
        if coords:
            folium.Marker(location=coords, popup=port).add_to(ship_map)
    folium.PolyLine([get_port_coordinates(p) for p in best_route["route"] if get_port_coordinates(p)], color="red").add_to(ship_map)
    ship_map.save("ship_route_map.html")
    print("\n🗺 Ship Route Map Saved as 'ship_route_map.html'. Open it in your browser.")
except Exception as e:
    print(f"⚠️ Could not generate map: {e}")
