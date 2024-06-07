{% urls_to_js %}

// /different/143/emma
const urls = new URLResolver();
console.log(urls.reverse('different', {kwargs: {'arg1': 143, 'arg2': 'emma'}}));

// reverse also supports query parameters
// /different/143/emma?intarg=0&listarg=A&listarg=B&listarg=C
console.log(urls.reverse(
    'different',
    {
        kwargs: {arg1: 143, arg2: 'emma'},
        query: {
            intarg: 0,
            listarg: ['A', 'B', 'C']
        }
    }
));
