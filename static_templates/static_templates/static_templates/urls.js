{% load static_templates %}
"use strict";

class URLPattern {

    constructor (qName, url, optionMap={}, optionDefaults={}) {
        this.qName = qName;
        this.url = url;
        this.optionMap = optionMap;
        this.optionDefaults = optionDefaults;
    }

    reverse (options={}) {
        for (const [opt, value] of Object.entries(this.optionDefaults)) {
            if (!options.hasOwnProperty(opt)) {
                options[opt] = value;
            }
        }
    }
}

class URLResolver {

    constructor() {
        this.registry = {};
    }

    reverse (qName, options={}) {
        if (this.registry.hasOwnProperty(qName)) {

        }
    }

    register (qName, url, option_map={}) {
        if (!this.registry.hasOwnProperty(qName)) {

        }
        this.registry[qName]
    }
};

{% block registrations %}
const {{ resolver_var|default:'urls' }} = new URLResolver();

{% register_urls %}

{% endblock registrations %}
