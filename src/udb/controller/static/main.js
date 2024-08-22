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
