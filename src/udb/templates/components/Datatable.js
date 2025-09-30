/**
 * BFH Science Self-Service Portal
 * Copyright (C) 2025 IKUS Software
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
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

/* Throw a JavaScript error. */
$.fn.dataTable.ext.errMode = 'throw';

$.fn.dataTable.rowGroupRender = $.fn.dataTable.rowGroupRender || {};

/**
 * Buttons to filter content of datatable.
 *
 * Options:
 * - search: Define the search criteria when filter is active
 * - search_off: Define the search criteria when filter is not active (optional)
 * - regex: True to enable regex lookup (optional)
 * - multi: True to enablemultiple selection for the same column.
 */
$.fn.dataTable.ext.buttons.filter = {
    init: function(dt, node, config) {
        if (config.search_off && config.multi) {
            console.error('search_off and multi are not supported together');
        }
        const that = this;
        dt.on('search.dt', function() {
            let activate;
            const curSearch = dt.column(config.column).search();
            if (config.multi) {
                const terms = curSearch.replace(/^\(/, '').replace(/\)$/, '').split('|');
                activate = terms.includes(config.search);
            } else {
                activate = dt.column(config.column).search() === config.search;
            }
            that.active(activate);
        });
    },
    action: function(e, dt, node, config) {
        const curSearch = dt.column(config.column).search();
        let terms = curSearch.replace(/^\(/, '').replace(/\)$/, '').split('|').filter(item => item !== '');
        if (node.hasClass('active')) {
            if (config.search_off) {
                // Disable - replace by our search_off pattern
                terms = [config.search_off];
            } else {
                // Disable - remove from term.
                terms = terms.filter(item => item != config.search)
            }
        } else if (config.multi) {
            // Enable - add new terms
            terms.push(config.search)
        } else {
            // Enable - replace all terms
            terms = [config.search];
        }
        let search;
        if (terms.length == 0) {
            search = '';
        } else if (terms.length == 1) {
            search = terms[0];
        } else {
            search = '(' + terms.join('|') + ')';
        }
        dt.column(config.column).search(search, true);
        dt.draw(true);
    }
};
$.fn.dataTable.ext.buttons.btnfilter = {
    extend: 'filter',
    className: 'cdt-btn-filter'
};
$.fn.dataTable.ext.buttons.collectionfilter = {
    align: 'button-right',
    autoClose: true,
    background: false,
    extend: 'collection',
    className: 'cdt-btn-collectionfilter',
    init: function(dt, node, config) {
        const that = this;
        dt.on('search.dt', function() {
            const activate = dt.column(config.column).search() !== '';
            that.active(activate);
        });
    },
};
/**
 * Button to reset the filters of datatable.
 * Default settings are restored using init() API.
 */
$.fn.dataTable.ext.buttons.reset = {
    text: 'Reset',
    action: function(e, dt, node, config) {
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
/**
 * Default render
 */
$.fn.dataTable.render.button = function ({
  label = 'changeme',
  className = 'btn btn-sm btn-primary btn-hover text-nowrap',
  ...attrs
} = {}) {
  const { escapeHtml } = DataTable.util;

  const attr = (name, value) => {
    if (value == null || value === false) return '';
    if (value === true) return ` ${name}`;
    return ` ${name}="${escapeHtml(String(value))}"`;
  };

  return {
    display: function (data, type, row, meta) {
      if (!data) return '';

      const href = encodeURI(String(data));

      // If caller supplies `class`, prefer it over className
      const { class: clsFromAttrs, ...rest } = attrs;
      const classValue = clsFromAttrs ?? className;

      const known = attr('class', classValue);

      const extra = Object.entries(rest)
        .map(([k, v]) => attr(k, v))
        .join('');

      return `<a${known}${extra} href="${escapeHtml(href)}">${escapeHtml(label)}</a>`;
    },
  };
};
$.fn.dataTable.render.choices = function(choices) {
    let lookup = null;
    if (Array.isArray(choices)) {
        // Convert array of tuples to a lookup object
        lookup = Object.fromEntries(choices);
    } else if (typeof choices === "object" && choices !== null) {
        // Already a dictionary
        lookup = choices;
    }
    return {
        display: function(data, type, row, meta) {
            return (lookup && data in lookup) ? lookup[data] : data;
        },
    };
}

// Build a child-row table showing only the hidden columns
$.fn.dataTable.Responsive.renderer.tableHidden =  function (options) {
  options = $.extend(
    {
      tableClass: '',
      empty: '—' // placeholder when a hidden cell is empty
    },
    options
  );

  return function (api, rowIdx, columns) {
    const data = $.map(columns, function (col) {
      if (!col.hidden) {
        return '';
      }

      const klass = col.className
        ? 'class="' + col.className + '"'
        : '';

      const title =
        '' !== col.title
          ? col.title + ':'
          : '';

      // Treat null/undefined/empty-string as empty
      const cell =
        col.data !== null &&
        col.data !== undefined &&
        col.data !== ''
          ? col.data
          : options.empty;

      return (
        '<tr ' +
        klass +
        ' data-dt-row="' +
        col.rowIndex +
        '" data-dt-column="' +
        col.columnIndex +
        '">' +
        '<th class="dtr-title-cell">' +
        title +
        '</th> ' +
        '<td class="dtr-data-cell">' +
        cell +
        '</td>' +
        '</tr>'
      );
    }).join('');

    // If there are no hidden columns, return false so no child row is shown
    return data
      ? $(
          '<table class="' +
            options.tableClass +
            ' dtr-details" width="100%"/>'
        ).append(data)
      : false;
  };
}

// Resolve one spec (render/startRender/endRender) into a callable
function resolveRenderSpec(source, key) {
    if (!source || !key || source[key] == null) return;

    const value = source[key];
    let fn;

    if (typeof value === 'function') {
        // Case A: already a function — use as-is
        fn = value;
    } else {
        // Case B: value is a string naming a render factory, e.g. 'number', 'text', 'ellipsis', 'myPlugin'
        const factoryName = value;
        let renderNS;
        if(key == 'render') {
            renderNS = $.fn.dataTable?.render;
        } else if(key == 'startRender' || key == 'endRender') {
            renderNS = $.fn.dataTable?.rowGroupRender;
        } else if(key == 'renderer') {
            renderNS = $.fn.dataTable?.Responsive?.renderer;
        }
        
        const factory = renderNS?.[factoryName];
        if (typeof factory !== 'function') {
            console.warn(`DataTables render factory '${factoryName}' not found`);
            return;
        }

        // Support kwargs | args | arg
        if (source[`${key}_kwargs`]) {
            fn = factory({...source[`${key}_kwargs`]});
        } else if (source[`${key}_args`]) {
            fn = factory(...source[`${key}_args`]);
        } else if (Object.hasOwn(source, `${key}_arg`)) {
            fn = factory(source[`${key}_arg`]);
        } else {
            fn = factory();
        }
    }

    return fn;
}

jQuery(function() {
    $('table[data-ajax]').each(function(_idx) {
        /* Load column properties */
        let columns = $(this).attr('data-columns');
        $(this).removeAttr('data-columns');
        columns = JSON.parse(columns);
        $.each(columns, function(_index, item) {
            item.render = resolveRenderSpec(item, 'render');
        });

        /* Process rowGroup render */
        let rowGroup = $(this).attr('data-row-group');
        $(this).removeAttr('data-row-group');
        rowGroup = JSON.parse(rowGroup);
        if(rowGroup && typeof rowGroup === 'object') {
            rowGroup.startRender = resolveRenderSpec(rowGroup, 'startRender');
            rowGroup.endRender = resolveRenderSpec(rowGroup, 'endRender');
        }

        /* Process responsive details render */
        let responsive = $(this).attr('data-responsive');
        $(this).removeAttr('data-responsive');
        responsive = JSON.parse(responsive);
        if(responsive && typeof responsive === 'object') {
            responsive.renderer = resolveRenderSpec(responsive, 'renderer');
        }

        let searchCols = columns.map(function(item, _index) {
            if (item.search !== undefined) {
                return {
                    "search": item.search,
                    "regex": item.regex || false
                };
            }
            return null;
        });
        let dt = $(this).DataTable({
            columns: columns,
            rowGroup: rowGroup,
            responsive: responsive,
            searchCols: searchCols,
            drawCallback: function(_settings) {
                // This callback show or hide the pagination when required
                if (_settings.aanFeatures.p) {
                    if (_settings._iDisplayLength > _settings.fnRecordsDisplay()) {
                        $(_settings.aanFeatures.p[0]).parent().hide();
                    } else {
                        $(_settings.aanFeatures.p[0]).parent().show();
                    }
                }
                // This callback is responsible to add and remove 'sorting-x-x' class
                // to allow CSS customization of the table based on the sorted column
                this.removeClass(function(_index, className) {
                    return className.split(/\s+/).filter(function(c) {
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
            initComplete: function() {
                // Remove no-footer class to fix CSS display with bootstrap5
                $(this).removeClass("no-footer");
                // If searching is enabled, focus on search field.
                $("div.dataTables_filter input").focus();
                // Trigger responsive recalculation on window resize
                $(window).on('resize', function() {
                    dt.columns.adjust().responsive.recalc();
                });
            },
            processing: true,
            deferRender: true,
        });
    });
});