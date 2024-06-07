{% enums_to_js "tests.examples.models" %}

console.log(Color.BLUE === Color.get('B'));
for (const color of Color) {
    console.log(color);
}
