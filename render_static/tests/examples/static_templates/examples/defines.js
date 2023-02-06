const defines = {
{% modules_to_js modules="render_static.tests.examples.models" level=1 %}
};
console.log(JSON.stringify(defines));
