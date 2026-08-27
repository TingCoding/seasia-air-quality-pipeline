{#
    Persists the outcome of every dbt test into audit.data_quality_log.

    Without this, test results live only in the terminal and disappear when the
    window closes. Writing them to a table makes data quality something you can
    query over time -- which check fails most often, whether a problem is new or
    long-standing, and whether a fix actually held.

    Wired up via on-run-end in dbt_project.yml.
#}

{% macro log_dbt_results(results) %}

    {% if not execute %}
        {{ return('') }}
    {% endif %}

    {% if results is none or results | length == 0 %}
        {{ return('') }}
    {% endif %}

    {% set rows = [] %}

    {% for res in results %}
        {% if res.node.resource_type == 'test' %}

            {% set check_name = res.node.name %}

            {#- the model a test points at, when dbt can resolve it -#}
            {% set target = res.node.depends_on.nodes[0] if res.node.depends_on.nodes
                            else 'unknown' %}

            {% set failures = res.failures if res.failures is not none else 0 %}

            {% set detail = (res.message | string | replace("'", "''"))[:500]
                            if res.message else '' %}

            {% set row %}
                (
                    '{{ check_name }}',
                    '{{ target }}',
                    '{{ res.status }}',
                    {{ failures }},
                    '{{ detail }}'
                )
            {% endset %}

            {% do rows.append(row) %}

        {% endif %}
    {% endfor %}

    {% if rows | length == 0 %}
        {{ return('') }}
    {% endif %}

    {% set insert_statement %}
        insert into audit.data_quality_log
            (check_name, target_table, status, failed_rows, detail)
        values
            {{ rows | join(',\n') }}
    {% endset %}

    {% do run_query(insert_statement) %}
    {{ log("Logged " ~ rows | length ~ " test results to audit.data_quality_log", info=True) }}

{% endmacro %}
