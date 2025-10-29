/**
 * Control showif
 */
jQuery(function() {
    function escape(v) {
        return v.replace(/(:|\.|\[|\]|,|=)/g, "\\$1");
    }
    $('[data-showif-field]').each(function() {
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
                const parent = elem.closest('.form-field');
                if (!parent.hasClass('collapse')) {
                    parent.addClass('collapse');
                    if (visible) {
                        parent.addClass('show');
                    }
                }
                // Update widget visibility accordingly.
                let collapsible = bootstrap.Collapse.getOrCreateInstance(parent, {
                    toggle: false
                });
                if (visible) {
                    collapsible.show();
                    elem.removeAttr('disabled');
                } else {
                    collapsible.hide();
                    elem.attr('disabled', '1');
                }
            }
            // Attach event to field.
            fieldElem.change(function() {
                updateShowIf();
            })
            updateShowIf();
        }
    });
});