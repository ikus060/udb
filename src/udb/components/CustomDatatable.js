jQuery(function() {

    /**
     * Escape string value.
     */
    function safe(data) {
        return String(data).replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    /**
    * Convert a string to a date. This function support the following input:
    * - full ISO format
    * - epoch as number or string
    * - YYYY-MM-dd
    */
    const DATE_PATTERN = /^(\d\d\d\d)(\-)?(\d\d)(\-)?(\d\d)$/i;

    function toDate(n) {
        let matches, year, month, day;
        if (typeof n === "number") {
            n = new Date(n * 1000); // epoch
        } else if (typeof n === 'string' && (matches = n.match(DATE_PATTERN))) {
            year = parseInt(matches[1], 10);
            month = parseInt(matches[3], 10) - 1;
            day = parseInt(matches[5], 10);
            return new Date(year, month, day);
        } else if (n) { // str
            n = isNaN(n) ? new Date(n) : new Date(parseInt(n) * 1000);
        }
        return n;
    }

    $.fn.dataTable.render.datetime = function () {
        return {
            display: function (data, type, row, meta) {
                const api = new $.fn.dataTable.Api(meta.settings);
                const date = toDate(data);
                const localDate = date ? safe(date.toLocaleString()) : '';
                /* Format date as 2 month ago */
                const seconds = Math.floor((new Date() - date) / 1000);
                const years = seconds / 31536000;
                const months = seconds / 2592000;
                const days = seconds / 86400;
                const hours = seconds / 3600;
                const minutes = seconds / 60;
                let relativeDate;
                if (years > 1) {
                    relativeDate = api.settings().i18n("udb.years", "%d years ago", Math.floor(years));
                } else if (months > 1) {
                    relativeDate = api.settings().i18n("udb.months", "%d months ago", Math.floor(months));
                } else if (days > 1) {
                    relativeDate = api.settings().i18n("udb.days", "%d days ago", Math.floor(days));
                } else if (hours > 1) {
                    relativeDate = api.settings().i18n("udb.hours", "%d hours ago", Math.floor(hours));
                } else if (minutes > 1) {
                    relativeDate = api.settings().i18n("udb.minutes", "%d minutes ago", Math.floor(minutes));
                } else {
                    relativeDate = api.settings().i18n("udb.seconds", "%d seconds ago", Math.floor(seconds));
                }
                return `<time datetime="${date}" title="${localDate}">${relativeDate}</time>`;
            },
            sort: function (data, type, row, meta) {
                const date = toDate(data);
                return date ? date.getTime() : 0;
            }
        };
    }

    /**
    * Render for record history.
    */
    $.fn.dataTable.render.changes = function () {
        return {
            display: function (data, type, row, meta) {
                const api = new $.fn.dataTable.Api(meta.settings);
                let html = '';
                const body_idx = api.column('body:name').index();
                if (body_idx && row[body_idx]) {
                    html += safe(row[body_idx]);
                }
                const type_idx = api.column('type:name').index();
                if (data) {
                    const null_value = api.settings().i18n(`udb.field.null`, 'undefined')
                    html += '<ul class="mb-0">';
                    if (row[type_idx] === 'new') {
                        /* For new record display only the new value. */
                        for (const [key, values] of Object.entries(data)) {
                            const field_name = safe(api.settings().i18n(`udb.field.${key}`, key));
                            if(values[1] !== null ) {
                                const new_value = safe(api.settings().i18n(`udb.value.${key}.${values[1]}`, `${values[1]}` )) ;
                                html += '<li><strong>' + field_name + '</strong>: ' + new_value + ' </li>';
                            }
                        }
                    } else {
                        /* For updates, display old and new value */
                        for (const [key, values] of Object.entries(data)) {
                            const field_name = safe(api.settings().i18n(`udb.field.${key}`, key));
                            html += '<li><strong>' + field_name + '</strong>: '
                            if (Array.isArray(values[0])) {
                                for (const deleted of values[0]) {
                                    html += '<br/> - ' + safe(deleted);
                                }
                                for (const added of values[1]) {
                                    html += '<br/> + ' + safe(added);
                                }
                            } else {
                                const old_value = safe(api.settings().i18n(`udb.value.${key}.${values[0]}`, `${values[0] !== null ? values[0] : undefined }`)) ;
                                const new_value = safe(api.settings().i18n(`udb.value.${key}.${values[1]}`, `${values[1] !== null ? values[1] : undefined }`)) ;
                                html += old_value + ' → ' + new_value + '</li>';
                            }
                        }
                    }
                    html += '</ul>';
                }
                return html;
            }
        };
    }

    $.fn.dataTable.render.message_body = function () {

        const datetime = $.fn.dataTable.render.datetime().display;

        const changes = $.fn.dataTable.render.changes().display;

        return {
            display: function (data, type, row, meta) {
                const api = new $.fn.dataTable.Api(meta.settings);
                let html = '';

                const type_idx = api.column('type:name').index();
                if (type_idx) {
                    const type = row[type_idx];
                    html += api.settings().i18n(`udb.value.type.${type}`, type);
                }

                const author_idx = api.column('author:name').index();
                if (author_idx) {
                    html += ' <em>' + row[author_idx] + '</em> • ';
                }

                const date_idx = api.column('date:name').index();
                if (date_idx) {
                    html += datetime(row[date_idx], type, row, meta);
                }

                html += '<br />' + changes(data, type, row, meta);
                return html;
            },
            sort: function (data, type, row, meta) {
                const api = new $.fn.dataTable.Api(meta.settings);
                const date_idx = api.column('date:name').index();
                const value = toDate(row[date_idx]);
                return value ? value.getTime() : 0;
            },
        };
    }

    $.fn.dataTable.render.primary_range = function () {
        return {
            display: function (data, type, row, meta) {
                let html = '<a href="' + encodeURI(row[row.length - 1]) + '" class="depth-' + safe(row[3]) + '">' +
                    '<i class="bi bi-diagram-3-fill me-1" aria-hidden="true"></i>' +
                    '<strong>' + safe(data) + '</strong>' +
                    '</a> ';
                const api = new $.fn.dataTable.Api(meta.settings);
                const status_idx = api.column('status:name').index();
                if (status_idx) {
                    if (row[status_idx] == 1) {
                        html += ' <span class="badge bg-warning">' + api.settings().i18n('udb.status.disabled') + '</span>';
                    } else if (row[status_idx] == 0) {
                        html += ' <span class="badge bg-danger">' + api.settings().i18n('udb.status.deleted') + '</span>';
                    }
                }
                return html;
            },
            sort: function (data, type, row, meta) {
                return row[2];
            },
        };
    }
    $.fn.dataTable.render.summary = function (render_arg) {
        /* FIXME Need to make this list canonical */
        let icon_table = {
            'dnszone': 'bi-collection',
            'subnet': 'bi-diagram-3-fill',
            'dhcprecord': 'bi-pin',
            'dnsrecord': 'bi-signpost-split-fill',
            'ip': 'bi-geo-fill',
            'mac': 'bi-ethernet',
            'user': 'bi-person-fill',
            'vrf': 'bi-layers',
            'deployment': 'bi-cloud-upload-fill',
            'environment': 'bi-terminal-fill',
            'rule': 'bi-ui-checks'
        };

        const model_name = typeof render_arg === 'string' ? render_arg : null;
        const model_name_column = render_arg?.model_name_column || 'model_name:name';
        const url_column = render_arg?.url_column || 'url:name';

        return {
            display: function (data, type, row, meta) {
                if (!data) return '-';
                const api = new $.fn.dataTable.Api(meta.settings);
                /* Get model_name from arguments or from row data */
                let effective_model_name = model_name;
                if (effective_model_name == null) {
                    const model_idx = api.column(model_name_column).index();
                    if (model_idx) {
                        effective_model_name = row[model_idx];
                    }
                }

                /* Define the URL */
                let url = "#";
                const url_idx = api.column(url_column).index();
                if (url_idx) {
                    url = encodeURI(row[url_idx])
                }

                let html = '<a href="' + url + '">' +
                    '<i class="bi ' + icon_table[effective_model_name] + ' me-1" aria-hidden="true"></i>' +
                    '<strong>' + safe(data).replace(/\./g, '.<wbr>') + '</strong>' +
                    '</a>';

                /* add label with status if available */
                const status_idx = api.column('status:name').index();
                if (status_idx) {
                    if (row[status_idx] == 1) {
                        html += ' <span class="badge bg-warning">' + api.settings().i18n('udb.status.disabled') + '</span>';
                    } else if (row[status_idx] == 0) {
                        html += ' <span class="badge bg-danger">' + api.settings().i18n('udb.status.deleted') + '</span>';
                    }
                }
                return html;
            },
            sort: function (data, type, row, meta) {
                return data;
            }
        };
    }
})