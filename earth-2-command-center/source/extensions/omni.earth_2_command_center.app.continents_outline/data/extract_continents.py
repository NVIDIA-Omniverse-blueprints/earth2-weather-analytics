
import json
import cartopy.feature as cfeature

if __name__ == "__main__":
    countries = cfeature.NaturalEarthFeature(
        category='cultural',
        name='admin_0_countries',
        scale='50m',
        facecolor='none',
        edgecolor='black'
    )

    coastline = cfeature.COASTLINE

    result = {
        "type": "FeatureCollection",
        "features": [],
    }

    for geom in coastline.geometries():
        feature = {
            "type": "Feature",
            "geometry": {
                "type": geom.geom_type,
                "coordinates": list(geom.coords)
            }
        }
        result["features"].append(feature)

    with open('coastline.geojson', 'w') as f:
        json.dump(result, f)
