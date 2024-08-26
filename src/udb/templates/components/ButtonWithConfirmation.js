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