/**
 * udb, A web interface to manage IT network
 * Copyright (C) 2022 IKUS Software inc.
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

/**
 * Convert a value to a date.
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

/**
 * Handle local datetime using <time datetime="value"></time>. 
 * Uses the value of `datetime` to converted it into local timezone. 
 * Class `js-date` could be used to only display the date portion. e.g.: 2021-05-28
 * Class `js-datetime` could be used to display the date and time portion e.g.: 2021-05-28 1:04pm
 * Class `js-time` could be used to display the time portion. e.g.: 1:04 pm
 */
jQuery(function () {

    $('time[datetime]').each(function () {
        const t = $(this);
        const d = toDate(t.attr('datetime'));
        if (t.hasClass("js-date")) {
            t.attr('title', d.toLocaleDateString());
            t.text(d.toLocaleDateString());
        } else if ($(this).hasClass("js-datetime")) {
            t.attr('title', d.toLocaleString());
            t.text(d.toLocaleString());
        } else if ($(this).hasClass("js-time")) {
            t.attr('title', d.toLocaleString());
            t.text(d.toLocaleTimeString());
        } else {
            t.attr('title', d.toLocaleString());
        }
    })

});
/**
 * Prompt user before form submit
 */
jQuery(function () {
    $('form[data-confirm]').submit(function (event) {
        const t = $(this);
        if (!confirm(t.attr('data-confirm'))) {
            event.preventDefault();
        }
    });
});

/**
 * Control showif
 */
jQuery(function () {
    $('[data-showif-field]').each(function () {
        function escape(v) {
            return v.replace(/(:|\.|\[|\]|,|=)/g, "\\$1");
        }
        const elem = $(this);
        const field = $(this).data('showif-field');
        const operator = $(this).data('showif-operator');
        const value = $(this).data('showif-value');
        // Lookup field
        if (!field) {
            return;
        }
        const fieldElem = $("[name='" + escape(field) + "']");
        if (fieldElem.length > 0) {
            function updateShowIf() {
                const curValue = fieldElem.val();
                let visible = false;
                if (operator == 'eq') {
                    visible = curValue == value;
                } else if (operator == 'ne') {
                    visible = curValue != value;
                } else if (operator == 'in' && Array.isArray(value)) {
                    visible = $.inArray(curValue, value) >= 0;
                }
                // To handle the initial state, manually add the collapse class before creating the collapsable class.
                const parent = elem.parent();
                if (!parent.hasClass('collapse')) {
                    parent.addClass('collapse');
                    if (visible) {
                        parent.addClass('show');
                    }
                }
                // Update widget visibility accordingly.
                let collapsible = bootstrap.Collapse.getOrCreateInstance(elem.parent(), { toggle: false });
                if (visible) {
                    collapsible.show();
                } else {
                    collapsible.hide();
                }
            }
            fieldElem.change(function () {
                updateShowIf();
            })
            updateShowIf();
        }
    });
});

/**
 * Buttons to filter content of datatable.
 * 
 * Options:
 * - search: Define the search criteria when filter is active
 * - search_off: Define the search criteria when filter is not active (optional)
 * - regex: True to enable regex lookup (optional)
 */
$.fn.dataTable.ext.buttons.filter = {
    text: 'Filter',
    className: 'udb-btn-filter',
    action: function (e, dt, node, config) {
        if (node.hasClass('active')) {
            dt.column(config.column).search(config.search_off || '', config.regex);
        } else {
            dt.column(config.column).search(config.search, config.regex);
        }
        dt.draw(true);
    }
};

/**
 * Button to reset the filters of datatable.
 * Default settings are restored using init() API.
 */
$.fn.dataTable.ext.buttons.clear = {
    text: 'Clear',
    action: function (e, dt, node, config) {
        dt.search('');
        if (dt.init().aoSearchCols) {
            const searchCols = dt.init().aoSearchCols;
            for (let i = 0; i < searchCols.length; i++) {
                const search = searchCols[i].search || "";
                dt.column(i).search(search);
            }
        } else {
            dt.columns().search('');
        }
        dt.draw(true);
    }
};

/** Default render */
function safe(data) {
    return typeof data === 'string' ?
        data.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;') :
        data;
}

$.fn.dataTable.render.action = function () {
    return {
        display: function (data, type, row, meta) {
            return '<a class="btn btn-primary btn-circle btn-hover" href="' + encodeURI(data) + '"><i class="bi bi-chevron-right" aria-hidden="true"></i><span class="visually-hidden">Edit</span></a>'
        },
    };
}

$.fn.dataTable.render.choices = function (choices) {
    return {
        display: function (data, type, row, meta) {
            for (const choice of choices) {
                if (choice[0] == data) {
                    return choice[1];
                }
            }
            return data;
        },
    };
}

$.fn.dataTable.render.datetime = function () {
    return {
        display: function (data, type, row, meta) {
            return toDate(data).toLocaleString();
        },
        sort: function (data, type, row, meta) {
            return toDate(data).getTime();
        }
    };
}

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
            html += '<ul class="mb-0">';
            if (row[type_idx] === 'new') {
                for (const [key, values] of Object.entries(data)) {
                    html += '<li><b>' + safe(key) + '</b>: ' + safe(values[1]) + ' </li>';
                }
            } else {
                for (const [key, values] of Object.entries(data)) {
                    html += '<li><b>' + safe(key) + '</b>: '
                    if (Array.isArray(values[0])) {
                        for (const deleted of values[0]) {
                            html += '<br/> - ' + safe(deleted);
                        }
                        for (const added of values[1]) {
                            html += '<br/> + ' + safe(added);
                        }
                    } else {
                        html += safe(values[0]) + ' → ' + safe(values[1]) + '</li>';
                    }
                }
            }
            html += '</ul>';
            return html;
        }
    };
}

$.fn.dataTable.render.message_body = function () {
    return {
        display: function (data, type, row, meta) {
            let html = '';
            if ('message_' + row.type in meta.settings.oLanguage) {
                html += meta.settings.oLanguage['message_' + row.type];
            } else {
                html += row.type;
            }
            html += '<em>' + row.author_name + '</em> • ';
            html += '<time datetime="' + row.date + '" title="' + toDate(row.date).toLocaleString() + '">' + row.date_lastupdated + '</time>';
            if (row.body) {
                html += '<br />' + safe(row.body);
            }
            switch (row.type) {
                case 'new':
                    html += '<ul class="mb-0">';
                    for (const [key, values] of Object.entries(row.changes)) {
                        html += '<li><b>' + safe(key) + '</b>: ' + safe(values[1]) + ' </li>';
                    }
                    html += '</ul>';
                    break;
                case 'dirty':
                    html += '<ul class="mb-0">';
                    for (const [key, values] of Object.entries(row.changes)) {
                        html += '<li><b>' + safe(key) + '</b>: '
                        if (Array.isArray(values[0])) {
                            for (const deleted of values[0]) {
                                html += '<br/> - ' + safe(deleted);
                            }
                            for (const added of values[1]) {
                                html += '<br/> + ' + safe(added);
                            }
                        } else {
                            html += safe(values[0]) + ' → ' + safe(values[1]) + '</li>';
                        }
                    }
                    html += '</ul>';
                    break;
            }
            return html;
        },
        sort: function (data, type, row, meta) {
            return toDate(row.date).getTime();
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
                if (row[status_idx] == 'disabled') {
                    html += ' <span class="badge bg-warning">' + meta.settings.oLanguage['disabled'] + '</span>';
                } else if (row[1] == 'deleted') {
                    html += ' <span class="badge bg-danger">' + meta.settings.oLanguage['deleted'] + '</span>';
                }
            }
            return html;
        },
        sort: function (data, type, row, meta) {
            return row[2];
        },
    };
}
$.fn.dataTable.render.summary = function (model_name = null) {
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
        'environment': 'bi-terminal-fill'
    };

    return {
        display: function (data, type, row, meta) {
            const api = new $.fn.dataTable.Api(meta.settings);
            /* Get model_name from arguments or from row data */
            let effective_model_name = model_name;
            if (effective_model_name == null) {
                const idx = api.column('model_name:name').index();
                if (idx) {
                    effective_model_name = row[idx];
                }
            }
            const url = encodeURI('url' in row ? row.url : row[row.length - 1]);
            let html = '<a href="' + url + '">' +
                '<i class="bi ' + icon_table[effective_model_name] + ' me-1" aria-hidden="true"></i>' +
                '<strong>' + safe(data) + '</strong>' +
                '</a>';
            const idx = api.column('status:name').index();
            if (idx) {
                if (row[idx] == 'disabled') {
                    html += ' <span class="badge bg-warning">' + meta.settings.oLanguage['disabled'] + '</span>';
                } else if (row[1] == 'deleted') {
                    html += ' <span class="badge bg-danger">' + meta.settings.oLanguage['deleted'] + '</span>';
                }
            }
            return html;
        },
        sort: function (data, type, row, meta) {
            return data;
        }
    };
}

jQuery(function () {
    $('table[data-ajax]').each(function (_idx) {
        /* Load column properties */
        let columns = $(this).attr('data-columns');
        $(this).removeAttr('data-columns');
        columns = JSON.parse(columns);
        $.each(columns, function (_index, item) {
            /* process the render attribute as a function. */
            if (item['render']) {
                if (item['render_arg']) {
                    item['render'] = $.fn.dataTable.render[item['render']](item['render_arg']);
                } else {
                    item['render'] = $.fn.dataTable.render[item['render']]();
                }
            }
            /* 
             * Patch column visibility for responsive<2.0.0 
             * Ref:https://datatables.net/extensions/responsive/classes
             */
            if ('visible' in item && !item['visible']) {
                item['className'] = 'never';
            }
        });
        let searchCols = columns.map(function (item, _index) {
            if (item.search) {
                return { "search": item.search, "regex": item.regex || False };
            }
            return null;
        });
        let dt = $(this).DataTable({
            columns: columns,
            searchCols: searchCols,
            drawCallback: function (_settings) {
                // This call back is responsible to add and remove 'sorting-x-x' class
                // to allow CSS customization of the table based on the sorted column
                this.removeClass(function (_index, className) {
                    return className.split(/\s+/).filter(function (c) {
                        return c.startsWith('sorted-');
                    }).join(' ');
                });
                // Add sorting class when sorting without filter
                if (this.api().order() && this.api().order()[0] && this.api().order()[0][0] >= 0 && this.api().search() === '') {
                    const colIdx = this.api().order()[0][0];
                    const direction = this.api().order()[0][1]
                    this.addClass('sorted-' + colIdx + '-' + direction);
                    const colName = _settings.aoColumns[colIdx].name;
                    if (colName) {
                        this.addClass('sorted-' + colName + '-' + direction);
                    }
                }
            },
            initComplete: function () {
                // Remove no-footer class to fix CSS display with bootstrap5
                $(this).removeClass("no-footer");
                // If searching is enabled, focus on search field.
                $("div.dataTables_filter input").focus();
            },
            processing: true,
            stateSave: true,
            deferRender: true,
        });
        // Update each buttons status
        dt.on('search.dt', function (e, settings) {
            dt.buttons().each(function (data, idx) {
                let conf = data.inst.s.buttons[idx].conf;
                if (conf && conf.column) {
                    dt.button(idx).active(dt.column(conf.column).search() === conf.search);
                }
            });
        });
    });
});