/* Initialize Typeahead */
jQuery(function() {
    $('.js-typeahead').each(function(_idx) {
        const cfg = $(this).data();
        const typeahead = $(this).typeahead(cfg);
        $(this).data('typeahead', typeahead);
    });
});
