/**
 * Typeahead configured using data-* attributes
 */
jQuery(function () {
    $('.js-typeahead').each(function (_idx) {
        const cfg = $(this).data();
        $(this).typeahead(cfg);
    });
});
