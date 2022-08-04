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
var DATE_PATTERN = /^(\d\d\d\d)(\-)?(\d\d)(\-)?(\d\d)$/i;
function toDate(n) {
    var matches, year, month, day;
    if (typeof n === "number") {
        n = new Date(n * 1000); // epoch
    } else if ((matches = n.match(DATE_PATTERN))) {
        year = parseInt(matches[1], 10);
        month = parseInt(matches[3], 10) - 1;
        day = parseInt(matches[5], 10);
        return new Date(year, month, day);
    } else { // str
        n = isNaN(n) ? new Date(n) : new Date(parseInt(n) * 1000);
    }
    return n;
}


$(document).ready(function () {
    /**
     * Handle local datetime using <time datetime="value"></time>. 
     * Uses the value of `datetime` to converted it into local timezone. 
     * Class `js-date` could be used to only display the date portion. e.g.: 2021-05-28
     * Class `js-datetime` could be used to display the date and time portion e.g.: 2021-05-28 1:04pm
     * Class `js-time` could be used to display the time portion. e.g.: 1:04 pm
     */
    $('time[datetime]').each(function () {
        var t = $(this);
        var d = toDate(t.attr('datetime'));
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

/** Filter button for DataTables */
$.fn.dataTable.ext.buttons.filter = {
    text: 'Filter',
    action: function (e, dt, node, config) {
        if (node.hasClass('active')) {
            dt.column(config.column).search('');
        } else {
            dt.column(config.column).search(config.search);
        }
        dt.draw(true);
    }
};
$.fn.dataTable.ext.buttons.clear = {
    text: 'Clear',
    action: function (e, dt, node, config) {
        dt.search('');
        dt.columns().search('');
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
            return '<a class="btn btn-primary btn-circle btn-hover" href="' + encodeURI(row.url) + '"><i class="bi bi-chevron-right" aria-hidden="true"></i><span class="visually-hidden">Edit</span></a>'
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
$.fn.dataTable.render.link = function () {
    return {
        display: function (data, type, row, meta) {
            return '<a href="' + encodeURI(row.url) + '">' + safe(data) + '</a>'
        },
    };
}
$.fn.dataTable.render.message_body = function () {
    return {
        display: function (data, type, row, meta) {
            let html = '';
            switch (row.type) {
                case 'new':
                    html += '<ul class="mb-0">';
                    for (const [key, values] of Object.entries(row.changes)) {
                        html += '<li><b>' + safe(key) + '</b>: ' + safe(values[1]) + ' </li>';
                    }
                    html += '</ul>';
                    return html;
                case 'dirty':
                    html +=
                        '<ul class="mb-0">';
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
                    return html;
                default:
                    return safe(row.body);
            }
        }
    };
}
$.fn.dataTable.render.subnet = function () {
    return {
        display: function (data, type, row, meta) {
            return '<a href="' + encodeURI(row.url) + '" class="depth-' + safe(row.depth) + '">' +
                '<i class="bi bi-diagram-3-fill me-1" aria-hidden="true"></i>' +
                '<strong>' + safe(data) + '</strong>' +
                '</a>';
        },
        sort: function (data, type, row, meta) {
            return row.order;
        }
    };
}
$.fn.dataTable.render.summary = function () {
    let icon_table = {
        'dnszone': 'bi-collection',
        'subnet': 'bi-diagram-3-fill',
        'dhcprecord': 'bi-ethernet',
        'dnsrecord': 'bi-signpost-split-fill',
        'ip': 'bi-geo-fill',
        'user': 'bi-person-fill',
        'vrf': 'bi-layers'
    };

    return {
        display: function (data, type, row, meta) {
            let html = '<a href="' + encodeURI(row.url) + '">' +
                '<i class="bi ' + icon_table[row.model_name] + ' me-1" aria-hidden="true"></i>' +
                '<strong>' + safe(data) + '</strong>' +
                '</a>';
            if (row.status == 'disabled') {
                html += ' <span class="badge bg-secondary">' + meta.settings.oLanguage['disabled'] + '</span>';
            } else if (row.status == 'deleted') {
                html += ' <span class="badge bg-danger">' + meta.settings.oLanguage['deleted'] + '</span>';
            }
            return html;
        },
        sort: function (data, type, row, meta) {
            return data;
        }
    };
}
$.fn.dataTable.render.user = function () {
    return {
        display: function (data, type, row, meta) {
            if (data) {
                return safe(data.fullname || data.username)
            } else {
                return '-';
            }
        },
        filter: function (data, type, row, meta) {
            if (data) {
                return data.username;
            } else {
                return null;
            }
        }
    };
}

$(document).ready(function () {
    $('table[data-ajax]').each(function (_idx) {
        /* Load column manually, to process the render attribute as a function. */
        let columns = $(this).attr('data-columns');
        $(this).removeAttr('data-columns');
        columns = JSON.parse(columns);
        $.each(columns, function (_index, item) {
            if (item['render']) {
                item['render'] = DataTable.render[item['render']]();
            }
        });
        let searchCols = columns.map(function (item, _index) {
            if (item.search) {
                return { "search": item.search };
            }
            return null;
        });
        let dt = $(this).DataTable({
            columns: columns,
            searchCols: searchCols,
            dom: "<'d-sm-flex align-items-center'<'mb-1 flex-grow-1'i><'mb-1'f><B>>" +
                "<'row'<'col-sm-12'rt>>",
            drawCallback: function (_settings) {
                // Remove sorting class
                this.removeClass(function (_index, className) {
                    return className.split(/\s+/).filter(function (c) {
                        return c.startsWith('sorted-');
                    }).join(' ');
                });
                // Add sorting class when sorting without filter
                if (this.api().order()[0][1] === 'asc' && this.api().order()[0][0] >= 0 && this.api().search() === '') {
                    this.addClass('sorted-' + this.api().order()[0][0]);
                }
            },
            initComplete: function () {
                $(this).removeClass("no-footer");
            },
            processing: true,
            responsive: true,
            stateSave: true,
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