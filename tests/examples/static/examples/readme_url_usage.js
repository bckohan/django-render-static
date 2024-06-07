
/**
 * A url resolver class that provides an interface very similar to 
 * Django's reverse() function. This interface is nearly identical to 
 * reverse() with a few caveats:
 *
 *  - Python type coercion is not available, so care should be taken to
 *      pass in argument inputs that are in the expect string format.
 *  - Not all reversal behavior can be replicated but these are corner 
 *      cases that are not likely to be correct url specification to 
 *      begin with.
 *  - The reverse function also supports a query option to include url
 *      query parameters in the reversed url.
 *
 * @class
 */
 class URLResolver {
	
	
	/**
	 * Instantiate this url resolver.
	 *
	 * @param {Object} options - The options object.
	 * @param {string} options.namespace - When provided, namespace will
	 *     prefix all reversed paths with the given namespace.
	 */
	constructor(options=null) {
		this.options = options || {};
		if (this.options.hasOwnProperty("namespace")) {
			this.namespace = this.options.namespace;
			if (!this.namespace.endsWith(":")) {
				this.namespace += ":";
			}
		} else {
			this.namespace = "";
		}
	}
	
	
	/**
	 * Given a set of args and kwargs and an expected set of arguments and
	 * a default mapping, return True if the inputs work for the given set.
	 *
	 * @param {Object} kwargs - The object holding the reversal named 
	 *     arguments.
	 * @param {string[]} args - The array holding the positional reversal 
	 *     arguments.
	 * @param {string[]} expected - An array of expected arguments.
	 * @param {Object.<string, string>} defaults - An object mapping 
	 *     default arguments to their values.
	 */
	#match(kwargs, args, expected, defaults={}) {
		if (defaults) {
			kwargs = Object.assign({}, kwargs);
			for (const [key, val] of Object.entries(defaults)) {
				if (kwargs.hasOwnProperty(key)) {
					if (kwargs[key] !== val && JSON.stringify(kwargs[key]) !== JSON.stringify(val) && !expected.includes(key)) { return false; }
					if (!expected.includes(key)) { delete kwargs[key]; }
				}
			}
		}
		if (Array.isArray(expected)) {
			return Object.keys(kwargs).length === expected.length && expected.every(value => kwargs.hasOwnProperty(value));
		} else if (expected) {
			return args.length === expected;
		} else {
			return Object.keys(kwargs).length === 0 && args.length === 0;
		}
	}
	
	
	/**
	 * Reverse a Django url. This method is nearly identical to Django's
	 * reverse function, with an additional option for URL parameters. See
	 * the class docstring for caveats.
	 *
	 * @param {string} qname - The name of the url to reverse. Namespaces
	 *   are supported using `:` as a delimiter as with Django's reverse.
	 * @param {Object} options - The options object.
	 * @param {string} options.kwargs - The object holding the reversal 
	 *   named arguments.
	 * @param {string[]} options.args - The array holding the reversal 
	 *   positional arguments.
	 * @param {Object.<string, string|string[]>} options.query - URL query
	 *   parameters to add to the end of the reversed url.
	 */
	reverse(qname, options={}) {
		if (this.namespace) {
			qname = `${this.namespace}${qname.replace(this.namespace, "")}`;
		}
		const kwargs = options.kwargs || {};
		const args = options.args || [];
		const query = options.query || {};
		let url = this.urls;
		for (const ns of qname.split(':')) {
			if (ns && url) { url = url.hasOwnProperty(ns) ? url[ns] : null; }
		}
		if (url) {
			let pth = url(kwargs, args);
			if (typeof pth === "string") {
				if (Object.keys(query).length !== 0) {
					const params = new URLSearchParams();
					for (const [key, value] of Object.entries(query)) {
						if (value === null || value === '') continue;
						if (Array.isArray(value)) value.forEach(element => params.append(key, element));
						else params.append(key, value);
					}
					const qryStr = params.toString();
					if (qryStr) return `${pth.replace(/\/+$/, '')}?${qryStr}`;
				}
				return pth;
			}
		}
		throw new TypeError(`No reversal available for parameters at path: ${qname}`);
	}
	
	urls = {
		"different": (kwargs={}, args=[]) => {
			if (this.#match(kwargs, args, ["arg1","arg2"])) { return `/different/${kwargs["arg1"]}/${kwargs["arg2"]}`; }
		},
		"simple": (kwargs={}, args=[]) => {
			if (this.#match(kwargs, args, ["arg1"])) { return `/simple/${kwargs["arg1"]}`; }
			if (this.#match(kwargs, args)) { return "/simple"; }
		},
	}
};


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
