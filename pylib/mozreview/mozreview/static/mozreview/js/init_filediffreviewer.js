$(document).ready(function() {
  var page = RB.PageManager.getPage();

  // Adjust the styling of comment blocks to draw attention to their
  // existance.  Unfortunately the template is opaque to us, so we
  // have to resort to MutationObserver shenanigans.
  try {
    var observer = new MutationObserver(function(mutations) {
      mutations.forEach(function(mutation) {
        var $target = $(mutation.target);
        if ($target.hasClass('diff-box')) {
          // initial page layout
          var $flags = $target.find('.commentflag');
          $flags
            .filter(':not(.draft)')
            .parents('tr')
            .addClass('comment-block-container');
          $flags
            .filter('.draft')
            .parents('tr')
            .addClass('comment-block-container-draft');
        } else if ($target.prop('nodeName') === 'TH') {
          // comment added/removed
          var $tr = $target.parent('tr');
          $tr
            .removeClass('comment-block-container')
            .removeClass('comment-block-container-draft');
          if ($target.find('.commentflag').length) {
            $tr.addClass($target.find('.commentflag.draft').length ?
                         'comment-block-container-draft' :
                         'comment-block-container');
          }
        }
      });
    });
    observer.observe(document.querySelector('#diffs'),
                     { childList: true, subtree: true });
  } catch (e) {
    // we don't care if this fails
  }

  var FileDiffReviewerData = $('#file-diff-reviewer-data')
                             .data('file-diff-reviewer');
  var fileDiffReviewerModels = FileDiffReviewerData.map(function(item) {
    return new RB.FileDiffReviewerModel(item);
  });
  var fileDiffReviewerCollection = new RB.FileDiffReviewerCollection(
    fileDiffReviewerModels
  );

  var getButtonText = function(elem) {
    if (elem.get('reviewed')) {
      return 'reviewed';
    } else {
      return 'not reviewed';
    }
  };

  var renderDiffButton = function() {
    $.funcQueue('diff_files').add(function() {
      fileDiffReviewerCollection.each(function(elem) {
        var diff_box_table = document.getElementById(
          'file' + elem.get('file_diff_id')
        );

        if (diff_box_table !== null) {
          var reviewButton = document.createElement('button');
          reviewButton.title = 'Click here to change the review status' +
                               ' of this file';
          reviewButton.textContent = getButtonText(elem);
          reviewButton.classList.add('diff-file-btn');
          if (elem.get('reviewed')) {
            reviewButton.classList.add('reviewed');
          }

          reviewButton.addEventListener('click', function(event) {
            reviewButton.disabled = true;
            elem.save({ reviewed: !elem.get('reviewed') },{
              success: function() {
                reviewButton.disabled = false;
                reviewButton.textContent = getButtonText(elem);
                reviewButton.classList.toggle('reviewed');
              },
              error: function(model, response) {
                reviewButton.disabled = false;
              }
            });
          });
          diff_box_table.parentElement.appendChild(reviewButton);
        }
      });
      $.funcQueue('diff_files').next();
    });
  };

  var currentRevision = page.model.get('revision');
  if (!currentRevision.get('isInterdiff')) {
    renderDiffButton();
  }
  // Listening to a route change seems to be the only way
  // to know if the user requested an interdiff or a revision
  // using the revision slider. The 'isInterdiff' property above
  // can only be used once on page load because it's not updated
  // when the user selects a different revision range using the slider.
  page.router.on('route:revision', function(revision) {
    // If the user requests an interdiff `revision` is a range of revision
    // numbers separated by a dash.
    if (revision.indexOf('-') === -1) {
      // We still need to wait for an update of the FileDiff collection
      // to make sure we trigger a render of the diff buttons AFTER
      // the DiffFile views are rendered.
      page.model.get('files').once('update', renderDiffButton);
    }
  });
});
