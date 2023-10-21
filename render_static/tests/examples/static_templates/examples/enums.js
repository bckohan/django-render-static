{% enums_to_js enums="render_static.tests.examples.models" %}

console.log(Color.BLUE === Color.get('B'));
for (const color of Color) {
    console.log(color);
}
