import xml.etree.ElementTree as ET
import pandas as pd
import folium
from folium.plugins import TimestampedGeoJson
from geopy.distance import geodesic
import json

# Fonction pour lire un fichier GPX et retourner un DataFrame
def lire_gpx(fichier):
    ns = {'default': 'http://www.topografix.com/GPX/1/1'}
    tree = ET.parse(fichier)
    root = tree.getroot()

    data = []
    for trkpt in root.findall('.//default:trkpt', ns):
        lat = float(trkpt.attrib['lat'])
        lon = float(trkpt.attrib['lon'])
        time_elem = trkpt.find('default:time', ns)
        if time_elem is not None:
            try:
                time = pd.to_datetime(time_elem.text, utc=True)
            except Exception:
                time = pd.NaT
            if pd.notna(time):
                data.append({'lat': lat, 'lon': lon, 'time': time})

    df = pd.DataFrame(data)
    df = df.dropna(subset=['time']).reset_index(drop=True)
    return df

# Calculer la vitesse et la distance cumulée
def ajouter_vitesse_distance(df):
    vitesses = [0]
    distances = [0]
    dist_cumul = 0
    for i in range(1, len(df)):
        pt1 = (df.loc[i-1, 'lat'], df.loc[i-1, 'lon'])
        pt2 = (df.loc[i, 'lat'], df.loc[i, 'lon'])
        dist = geodesic(pt1, pt2).meters
        dist_cumul += dist
        delta_t = (df.loc[i, 'time'] - df.loc[i-1, 'time']).total_seconds()
        vitesse = (dist / delta_t) * 3.6 if delta_t > 0 else 0
        vitesses.append(round(vitesse, 2))
        distances.append(round(dist_cumul / 1000, 2))
    df['vitesse_kmh'] = vitesses
    df['km'] = distances
    return df

# Charger les fichiers GPX
fichier1 = r"C:\Users\guill\OneDrive\Documents\Vélo\Fichiers GPX\GFNY_Guillaume.gpx"
fichier2 = r"C:\Users\guill\OneDrive\Documents\Vélo\Fichiers GPX\GFNY_Romain.gpx"
df1 = ajouter_vitesse_distance(lire_gpx(fichier1))
df2 = ajouter_vitesse_distance(lire_gpx(fichier2))

# Créer la carte
start_lat, start_lon = df1.iloc[0]['lat'], df1.iloc[0]['lon']
m = folium.Map(location=[start_lat, start_lon], zoom_start=14)

# Créer les features pour les deux coureurs
features1 = []
for i, row in df1.iterrows():
    features1.append({
        'type': 'Feature',
        'geometry': {'type': 'Point', 'coordinates': [row['lon'], row['lat']]},
        'properties': {
            'time': row['time'].strftime('%Y-%m-%dT%H:%M:%SZ'),
            'popup': f"Guillaume<br>Vitesse: {row['vitesse_kmh']} km/h<br>Distance: {row['km']} km",
            'icon': 'circle',
            'iconstyle': {'fillColor': 'blue', 'fillOpacity': 0.8, 'radius': 5},
            'vitesse': row['vitesse_kmh'],
            'km': row['km']
        }
    })

features2 = []
for i, row in df2.iterrows():
    features2.append({
        'type': 'Feature',
        'geometry': {'type': 'Point', 'coordinates': [row['lon'], row['lat']]},
        'properties': {
            'time': row['time'].strftime('%Y-%m-%dT%H:%M:%SZ'),
            'popup': f"Romain<br>Vitesse: {row['vitesse_kmh']} km/h<br>Distance: {row['km']} km",
            'icon': 'circle',
            'iconstyle': {'fillColor': 'red', 'fillOpacity': 0.8, 'radius': 5},
            'vitesse': row['vitesse_kmh'],
            'km': row['km']
        }
    })

features_total = features1 + features2

# Ajouter l'animation
tg = TimestampedGeoJson(
    {'type': 'FeatureCollection', 'features': features_total},
    period='PT1S',
    add_last_point=True,
    auto_play=False,
    loop=False,
    max_speed=1,
    loop_button=True,
    date_options='YYYY/MM/DD HH:mm:ss',
    time_slider_drag_update=True
)
tg.add_to(m)

# Ajouter l'affichage de l'écart et des vitesses
info_box = """
<style>
#infoBox {
    position: fixed;
    top: 65px;
    right: 15px;
    z-index: 9999;
    background: rgba(0, 0, 0, 0.75);
    color: white;
    padding: 10px 18px;
    border-radius: 10px;
    font-size: 16px;
    font-family: Arial, sans-serif;
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    line-height: 1.5;
}
</style>
<div id="infoBox">
    Écart de temps : <span id="gapValue">0</span> sec<br>
    Guillaume : <span id="gSpeed">0</span> km/h, <span id="gKm">0</span> km<br>
    Romain : <span id="rSpeed">0</span> km/h, <span id="rKm">0</span> km
</div>
"""
m.get_root().html.add_child(folium.Element(info_box))

# Script JavaScript
script_js = f"""
<script>
function getDistance(lat1, lon1, lat2, lon2) {{
    const R = 6371e3;
    const φ1 = lat1 * Math.PI/180, φ2 = lat2 * Math.PI/180;
    const Δφ = (lat2-lat1) * Math.PI/180, Δλ = (lon2-lon1) * Math.PI/180;
    const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) + Math.cos(φ1)*Math.cos(φ2)*Math.sin(Δλ/2)*Math.sin(Δλ/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}}

function findClosestFeature(features, lat, lon) {{
    let closest = null, minDist = Infinity;
    for (let f of features) {{
        let [lon2, lat2] = f.geometry.coordinates;
        let dist = getDistance(lat, lon, lat2, lon2);
        if (dist < minDist) {{
            minDist = dist;
            closest = f;
        }}
    }}
    return closest;
}}

function findFeatureByTime(timeStr, features) {{
    let target = new Date(timeStr).getTime();
    let closest = null, minDiff = Infinity;
    for (let f of features) {{
        let t = new Date(f.properties.time).getTime();
        let diff = Math.abs(t - target);
        if (diff < minDiff) {{ minDiff = diff; closest = f; }}
    }}
    return closest;
}}

const features1 = {json.dumps(features1)};
const features2 = {json.dumps(features2)};
const gapBox = document.getElementById('gapValue');
const gSpeed = document.getElementById('gSpeed');
const rSpeed = document.getElementById('rSpeed');
const gKm = document.getElementById('gKm');
const rKm = document.getElementById('rKm');

setTimeout(() => {{
    for (let key in window) {{
        if (window[key] instanceof L.Map) {{
            let map = window[key];
            if (!map.timeDimension) return;
            map.timeDimension.on('timeload', function(e) {{
                let currentTime = new Date(map.timeDimension.getCurrentTime());
                let iso = currentTime.toISOString().slice(0,19)+'Z';
                let f1 = findFeatureByTime(iso, features1);
                if (!f1) return;
                let [lon1, lat1] = f1.geometry.coordinates;
                let f2 = findClosestFeature(features2, lat1, lon1);
                if (!f2) return;
                let t1 = new Date(f1.properties.time);
                let t2 = new Date(f2.properties.time);
                let diff = Math.round((t1 - t2) / 1000);
                gapBox.innerHTML = (diff > 0 ? '+' : '') + diff + ' sec';
                gSpeed.innerHTML = f1.properties.vitesse.toFixed(1);
                gKm.innerHTML = f1.properties.km.toFixed(2);
                rSpeed.innerHTML = f2.properties.vitesse.toFixed(1);
                rKm.innerHTML = f2.properties.km.toFixed(2);
            }});
            break;
        }}
    }}
}}, 1000);
</script>
"""
m.get_root().html.add_child(folium.Element(script_js))

# Sauvegarder
m.save("Duel_Guillaume_Romain.html")
