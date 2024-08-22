/**
 * DualList Widget configure with class="multi"
 */
jQuery(function () {
    $('select.multi').each(function (_idx) {
        const cfg = $(this).data();
        $(this).multi(cfg);
    });
});