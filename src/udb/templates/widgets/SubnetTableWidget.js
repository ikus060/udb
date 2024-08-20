jQuery(function () {
    $('.udb-stw').each(function (_idx) {
        const stw = $(this);
        const table = stw.find('.table');
        const cfg = stw.data('stw');
        const row_html = cfg['row'];
        // Configure "Show Delete toggle".
        stw.on('click', '.udb-stw-toggle', function() {
            table.toggleClass('hide-deleted');
            stw.toggleClass('active');
        });
        // Configure "Add row" button.
        stw.on('click', '.udb-stw-add-row', function() {
          var tbody = $(table).children('tbody');
          var next_id = parseInt(tbody.children().last().attr('id').split('-')[1]) + 1
          tbody.append(row_html.replaceAll('TOKEN', next_id));
        });
        // Configure "Delete" / "Enable" buttons
        stw.on('click', '.udb-stw-toggle-row', function(){
          const row = $(this).closest('tr');
          const row_id = row.attr('id');
          const status = $('#' + row_id + '-status');
          if(status.val() == '2') {
            row.addClass('deleted');
            status.val(0);
          } else if(status.val()=='0') {
            row.removeClass('deleted');
            status.val(2);
          } else if(status.val()=='') {
            row.remove();
          }
        });
    });
});