{% load enum_test %}
{% block transpile_enums %}
{% enums_to_js enums=enums include_properties=include_properties exclude_properties=exclude_properties class_properties=class_properties properties=properties symmetric_properties=symmetric_properties isymmetric_properties=isymmetric_properties to_string=to_string|default_bool:True %}
{% endblock %}

{% enum_tests enums=test_enums|default:enums|enum_list class_properties=class_properties properties=test_properties|default:properties symmetric_properties=test_symmetric_properties|default:symmetric_properties class_name_map=class_name_map to_string=to_string|default_bool:True %}
