/* Clean jQuery helpers (no <script> wrapper) */
(function ($) {
  'use strict';

  // Run when DOM is ready
  $(function () {
    // 1) Keep dropdown open when clicking inside it
    $(document).on('click', '.dropdown-menu', function (e) {
      e.stopPropagation();
    });

    // 2) Radios: only the selected .js-check in a group stays "active"
    $(document).on('change', '.js-check :radio', function () {
      var groupName = $(this).attr('name');
      if (!groupName) return;

      $('input[type="radio"][name="' + groupName + '"]')
        .closest('.js-check')
        .removeClass('active');

      if (this.checked) {
        $(this).closest('.js-check').addClass('active');
      }
    });

    // 3) Checkboxes: toggle "active" on its .js-check container
    $(document).on('change', '.js-check :checkbox', function () {
      $(this).closest('.js-check').toggleClass('active', this.checked);
    });

    // 4) Bootstrap tooltips (supports v4 & v5)
    var $tooltipTargets = $('[data-toggle="tooltip"], [data-bs-toggle="tooltip"]');
    if ($tooltipTargets.length) {
      // Bootstrap 5
      if (window.bootstrap && typeof window.bootstrap.Tooltip === 'function') {
        $tooltipTargets.each(function () {
          new window.bootstrap.Tooltip(this);
        });
      }
      // Bootstrap 4 (jQuery plugin)
      else if (typeof $tooltipTargets.tooltip === 'function') {
        $tooltipTargets.tooltip();
      }
    }

    // 5) Auto-fade flash message if present
    var $msg = $('#message');
    if ($msg.length) {
      setTimeout(function () {
        $msg.fadeOut('slow');
      }, 4000);
    }
  });
})(window.jQuery);
