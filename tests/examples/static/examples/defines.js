const defines = {
	ExampleModel: {
		DEFINE1: "D1",
		DEFINE2: "D2",
		DEFINE3: "D3",
		DEFINES: [["D1", "Define 1"], ["D2", "Define 2"], ["D3", "Define 3"]],
		Color: {
			RED: "R",
			GREEN: "G",
			BLUE: "B",
		},
		MapBoxStyle: {
			STREETS: 1,
			OUTDOORS: 2,
			LIGHT: 3,
			DARK: 4,
			SATELLITE: 5,
			SATELLITE_STREETS: 6,
			NAVIGATION_DAY: 7,
			NAVIGATION_NIGHT: 8,
		},
	},
};

console.log(JSON.stringify(defines));
