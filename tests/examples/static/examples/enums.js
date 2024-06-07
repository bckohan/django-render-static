class Color {
	
	static RED = new Color("R", "RED", "Red", [1, 0, 0], "ff0000");
	static GREEN = new Color("G", "GREEN", "Green", [0, 1, 0], "00ff00");
	static BLUE = new Color("B", "BLUE", "Blue", [0, 0, 1], "0000ff");
	
	constructor (value, name, label, rgb, hex) {
		this.value = value;
		this.name = name;
		this.label = label;
		this.rgb = rgb;
		this.hex = hex;
	}
	
	toString() {
		return this.value;
	}
	
	static get(value) {
		if (value instanceof this) {
			return value;
		}
		
		for (const en of this) {
			if (en.value === value) {
				return en;
			}
		}
		throw new TypeError(`No Color enumeration maps to value ${value}`);
	}
	
	static [Symbol.iterator]() {
		return [Color.RED, Color.GREEN, Color.BLUE][Symbol.iterator]();
	}
}
class MapBoxStyle {
	
	static STREETS = new MapBoxStyle(1, "STREETS", "Streets", "streets", 11, "mapbox://styles/mapbox/streets-v11");
	static OUTDOORS = new MapBoxStyle(2, "OUTDOORS", "Outdoors", "outdoors", 11, "mapbox://styles/mapbox/outdoors-v11");
	static LIGHT = new MapBoxStyle(3, "LIGHT", "Light", "light", 10, "mapbox://styles/mapbox/light-v10");
	static DARK = new MapBoxStyle(4, "DARK", "Dark", "dark", 10, "mapbox://styles/mapbox/dark-v10");
	static SATELLITE = new MapBoxStyle(5, "SATELLITE", "Satellite", "satellite", 9, "mapbox://styles/mapbox/satellite-v9");
	static SATELLITE_STREETS = new MapBoxStyle(6, "SATELLITE_STREETS", "Satellite Streets", "satellite-streets", 11, "mapbox://styles/mapbox/satellite-streets-v11");
	static NAVIGATION_DAY = new MapBoxStyle(7, "NAVIGATION_DAY", "Navigation Day", "navigation-day", 1, "mapbox://styles/mapbox/navigation-day-v1");
	static NAVIGATION_NIGHT = new MapBoxStyle(8, "NAVIGATION_NIGHT", "Navigation Night", "navigation-night", 1, "mapbox://styles/mapbox/navigation-night-v1");
	
	static docs = "https://mapbox.com";
	
	constructor (value, name, label, slug, version, uri) {
		this.value = value;
		this.name = name;
		this.label = label;
		this.slug = slug;
		this.version = version;
		this.uri = uri;
	}
	
	toString() {
		return this.uri;
	}
	
	static get(value) {
		if (value instanceof this) {
			return value;
		}
		
		for (const en of this) {
			if (en.value === value) {
				return en;
			}
		}
		throw new TypeError(`No MapBoxStyle enumeration maps to value ${value}`);
	}
	
	static [Symbol.iterator]() {
		return [MapBoxStyle.STREETS, MapBoxStyle.OUTDOORS, MapBoxStyle.LIGHT, MapBoxStyle.DARK, MapBoxStyle.SATELLITE, MapBoxStyle.SATELLITE_STREETS, MapBoxStyle.NAVIGATION_DAY, MapBoxStyle.NAVIGATION_NIGHT][Symbol.iterator]();
	}
}


console.log(Color.BLUE === Color.get('B'));
for (const color of Color) {
    console.log(color);
}
