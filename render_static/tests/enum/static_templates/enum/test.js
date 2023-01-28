{% load enum_test %}
{% block enums %}
{% enum_to_js enum=enums include_properties=include_properties exclude_properties=exclude_properties class_properties=class_properties properties=properties symmetric_properties=symmetric_properties %}
{% endblock %}

{% enum_tests enums=enums|enum_list class_properties=class_properties properties=properties symmetric_properties=test_symmetric_properties %}
