$(window).on('load', function() {
  var documentSettings = {};

  const CHAPTER_ZOOM = 15;

  // Default newspaper colors
  var newspaperColors = {
    'EBT': '#e63946',
    'WSJ': '#6c757d',
    'NYT': '#0077b6',
    'SFC': '#f4a261',
    'UST': '#2a9d8f',
    'WLD': '#9c27b0',
    'STD': '#e76f51'
  };

  // Cache-busting with current timestamp down to millisecond
  var timestamp = Date.now();

  $.get('csv/Options.csv?time=' + timestamp, function(options) {
    $.get('csv/Chapters.csv?time=' + timestamp, function(chapters) {
      $.getJSON('csv/metadata.json?time=' + timestamp, function(metadata) {
        initMap(
          $.csv.toObjects(options),
          $.csv.toObjects(chapters),
          metadata
        );
      }).fail(function() {
        initMap(
          $.csv.toObjects(options),
          $.csv.toObjects(chapters),
          null
        );
      });
    }).fail(function(e) { alert('Found Options.csv, but could not read Chapters.csv'); });
  }).fail(function(e) {
    var parse = function(res) {
      return Papa.parse(Papa.unparse(res[0].values), {header: true}).data;
    };

    if (typeof googleDocURL !== 'undefined' && googleDocURL) {
      if (typeof googleApiKey !== 'undefined' && googleApiKey) {
        var apiUrl = 'https://sheets.googleapis.com/v4/spreadsheets/';
        var spreadsheetId = googleDocURL.split('/d/')[1].split('/')[0];

        $.when(
          $.getJSON(apiUrl + spreadsheetId + '/values/Options?key=' + googleApiKey),
          $.getJSON(apiUrl + spreadsheetId + '/values/Chapters?key=' + googleApiKey),
        ).then(function(options, chapters) {
          initMap(parse(options), parse(chapters), null);
        });
      } else {
        alert('You load data from a Google Sheet, you need to add a free Google API key');
      }
    } else {
      alert('You need to specify a valid Google Sheet (googleDocURL)');
    }
  });

  function createDocumentSettings(settings) {
    for (var i in settings) {
      var setting = settings[i];
      documentSettings[setting.Setting] = setting.Customize;
    }
  }

  function getSetting(s) {
    return documentSettings[constants[s]];
  }

  function trySetting(s, def) {
    s = getSetting(s);
    if (!s || s.trim() === '') { return def; }
    return s;
  }

  function addBaseMap() {
    var basemap = trySetting('_tileProvider', 'Stamen.TonerLite');
    L.tileLayer.provider(basemap, {
      maxZoom: 18,
      apiKey: trySetting('_tileProviderApiKey', ''),
      apikey: trySetting('_tileProviderApiKey', ''),
      key: trySetting('_tileProviderApiKey', ''),
      accessToken: trySetting('_tileProviderApiKey', '')
    }).addTo(map);
  }

  function hexToLightRgba(hex, alpha) {
    hex = hex.replace('#', '');
    if (hex.length === 3) hex = hex.split('').map(c => c + c).join('');
    var r = parseInt(hex.substring(0, 2), 16) || 0;
    var g = parseInt(hex.substring(2, 4), 16) || 0;
    var b = parseInt(hex.substring(4, 6), 16) || 0;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  function updateNewspaperBadgeStyles() {
    var styleStr = '';
    Object.keys(newspaperColors).forEach(paper => {
      var color = newspaperColors[paper];
      var bgLight = hexToLightRgba(color, 0.15);
      styleStr += `.np-badge-${paper.toLowerCase()} { background-color: ${bgLight} !important; color: ${color} !important; border-color: ${color} !important; }\n`;
    });
    $('#newspaper-dynamic-styles').remove();
    $('<style id="newspaper-dynamic-styles">').text(styleStr).appendTo('head');
  }

  function cleanStreetAddress(fullAddr) {
    if (!fullAddr) return '';
    var streetPart = fullAddr.split(',')[0].trim();
    // Convert to Title Case
    return streetPart.replace(/\w\S*/g, function(txt) {
      return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
    });
  }

  function initMap(options, chapters, metadata) {
    createDocumentSettings(options);
    var chapterContainerMargin = 70;

    document.title = getSetting('_mapTitle');
    $('#header').append('<h1>' + (getSetting('_mapTitle') || '') + '</h1>');
    $('#header').append('<h2>' + (getSetting('_mapSubtitle') || '') + '</h2>');

    if (metadata && metadata.upload_timestamp_pst) {
      $('#header').append('<div class="upload-pst-header"><i class="fa fa-clock"></i> Uploaded to GitHub: ' + metadata.upload_timestamp_pst + '</div>');
    } else {
      $('#header').append('<div class="upload-pst-header"><i class="fa fa-clock"></i> Uploaded: Recent (PST)</div>');
    }

    if (getSetting('_mapLogo')) {
      $('#logo').append('<img src="' + getSetting('_mapLogo') + '" />');
      $('#top').css('height', '60px');
    } else {
      $('#logo').css('display', 'none');
      $('#header').css('padding-top', '25px');
    }

    addBaseMap();

    if (getSetting('_zoomControls') !== 'off') {
      L.control.zoom({ position: getSetting('_zoomControls') }).addTo(map);
    }

    // Collect all unique detected newspapers
    var detectedNewspapers = new Set();
    chapters.forEach(c => {
      if (c['Newspapers']) {
        c['Newspapers'].split(/\s+/).forEach(p => {
          if (p.trim()) detectedNewspapers.add(p.trim().toUpperCase());
        });
      }
    });
    if (detectedNewspapers.size === 0) {
      ['EBT', 'WSJ', 'NYT', 'SFC'].forEach(p => detectedNewspapers.add(p));
    }

    updateNewspaperBadgeStyles();

    // -------------------------------------------------------------
    // DIV 1: Mobile-friendly Newspaper Color Picker (replaces container0)
    // -------------------------------------------------------------
    var colorPickerContainer = $('<div></div>', {
      id: 'container0',
      class: 'chapter-container in-focus'
    });

    var pickerCard = $('<div class="special-card-container"></div>');
    pickerCard.append('<div class="card-title"><i class="fa fa-palette"></i> Newspaper Color Options</div>');
    var pickerGrid = $('<div class="color-picker-grid"></div>');

    Array.from(detectedNewspapers).forEach(paper => {
      var color = newspaperColors[paper] || '#4a5568';
      newspaperColors[paper] = color;
      
      var item = $('<div class="picker-item"></div>');
      item.append(`<label for="picker_${paper}">${paper}</label>`);
      var input = $(`<input type="color" id="picker_${paper}" value="${color}">`);
      input.on('input change', function() {
        var newColor = $(this).val();
        newspaperColors[paper] = newColor;
        updateNewspaperBadgeStyles();
      });
      item.append(input);
      pickerGrid.append(item);
    });
    pickerCard.append(pickerGrid);
    colorPickerContainer.append(pickerCard);
    $('#contents').append(colorPickerContainer);

    // -------------------------------------------------------------
    // DIV 2: Addresses Found vs Not Found Stats (replaces container1)
    // -------------------------------------------------------------
    var statsContainer = $('<div></div>', {
      id: 'container1',
      class: 'chapter-container out-focus'
    });

    var foundCount = metadata ? metadata.addresses_found : chapters.length;
    var notFoundCount = metadata ? metadata.addresses_not_found : 0;

    var statsCard = $('<div class="special-card-container"></div>');
    statsCard.append('<div class="card-title"><i class="fa fa-list-check"></i> Address Resolution Summary</div>');
    statsCard.append(`
      <div class="stats-grid">
        <div class="stat-box found">
          <div class="stat-val">${foundCount}</div>
          <div class="stat-lbl">Addresses Found</div>
        </div>
        <div class="stat-box not-found">
          <div class="stat-val">${notFoundCount}</div>
          <div class="stat-lbl">Not Found / Problem</div>
        </div>
      </div>
    `);
    statsContainer.append(statsCard);
    $('#contents').append(statsContainer);

    // -------------------------------------------------------------
    // Address Containers (containers 2, 3, ...)
    // -------------------------------------------------------------
    var markers = [null, null]; // Offset for special containers 0 and 1
    var chapterCount = 0;

    for (var idx = 0; idx < chapters.length; idx++) {
      var c = chapters[idx];
      var containerIdx = idx + 2; // Offset by 2 for color picker & stats divs

      if (!isNaN(parseFloat(c['Latitude'])) && !isNaN(parseFloat(c['Longitude']))) {
        var lat = parseFloat(c['Latitude']);
        var lon = parseFloat(c['Longitude']);
        chapterCount += 1;

        markers.push(
          L.marker([lat, lon], {
            icon: L.ExtraMarkers.icon({
              icon: 'fa-number',
              number: c['Marker'] === 'Numbered' ? chapterCount : (c['Marker'] === 'Plain' ? '' : c['Marker']),
              markerColor: c['Marker Color'] || 'blue'
            }),
            opacity: c['Marker'] === 'Hidden' ? 0 : 0.9,
            interactive: c['Marker'] === 'Hidden' ? false : true,
          })
        );
      } else {
        markers.push(null);
      }

      var container = $('<div></div>', {
        id: 'container' + containerIdx,
        class: 'chapter-container out-focus'
      });

      var streetNameClean = cleanStreetAddress(c['Chapter']);
      var mapsUrl = c['Maps Link'] || (c['Chapter'] ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(c['Chapter'])}` : '#');

      var headerHtml = `<p class="chapter-header"><a href="${mapsUrl}" target="_blank" class="street-addr-link">${streetNameClean}</a></p>`;
      
      // Newspaper badges
      var papersStr = c['Newspapers'] || '';
      var paperBadgesHtml = '';
      if (papersStr.trim()) {
        paperBadgesHtml = '<div class="newspapers-row">';
        papersStr.trim().split(/\s+/).forEach(p => {
          var paperCode = p.toUpperCase();
          paperBadgesHtml += `<span class="np-badge np-badge-${paperCode.toLowerCase()}" data-paper="${paperCode}">${paperCode}</span>`;
        });
        paperBadgesHtml += '</div>';
      }

      // Miles to next address
      var milesVal = c['Miles to Next'] || c['Description'] || '';
      var milesHtml = '';
      if (milesVal && !isNaN(parseFloat(milesVal))) {
        milesHtml = `<div class="miles-to-next"><i class="fa fa-car"></i> ${parseFloat(milesVal).toFixed(1)} miles to next stop</div>`;
      } else if (c['Description'] && c['Description'].toLowerCase().includes('start')) {
        milesHtml = `<div class="miles-to-next"><i class="fa fa-flag-checkered"></i> Start Location</div>`;
      }

      // Mobile friendly button to scroll to next address
      var nextBtnHtml = `<button type="button" class="btn-next-address" data-target-idx="${containerIdx + 1}" onclick="handleNextAddressClick(this, ${containerIdx + 1})">Next Address <i class="fa fa-arrow-down"></i></button>`;

      container
        .append(headerHtml)
        .append(paperBadgesHtml)
        .append(milesHtml)
        .append(nextBtnHtml);

      $('#contents').append(container);
    }

    window.handleNextAddressClick = function(btnElem, targetIdx) {
      $(btnElem).addClass('pushed').html('Pushed <i class="fa fa-check"></i>');
      var targetDiv = $('#container' + targetIdx);
      if (targetDiv.length) {
        $('#contents').animate({
          scrollTop: targetDiv.offset().top + $('#contents').scrollTop() - 100
        }, 500);
      }
    };

    changeAttribution();

    // Scroll calculation across all container elements (0, 1, 2, ...)
    var totalDivs = chapters.length + 2;
    var pixelsAbove = [];
    pixelsAbove[0] = -100;
    for (var i = 1; i < totalDivs; i++) {
      pixelsAbove[i] = pixelsAbove[i-1] + $('div#container' + (i-1)).height() + chapterContainerMargin;
    }
    pixelsAbove.push(Number.MAX_VALUE);

    var currentlyInFocus = 0;
    $('div#contents').scroll(function() {
      var currentPosition = $(this).scrollTop();

      if (currentPosition < 200) {
        $('#title').css('opacity', 1 - Math.min(1, currentPosition / 100));
      }

      for (var i = 0; i < pixelsAbove.length - 1; i++) {
        if (currentPosition >= pixelsAbove[i] && currentPosition < (pixelsAbove[i+1] - 2 * chapterContainerMargin) && currentlyInFocus != i) {
          location.hash = i + 1;

          $('.chapter-container').removeClass("in-focus").addClass("out-focus");
          $('div#container' + i).addClass("in-focus").removeClass("out-focus");

          currentlyInFocus = i;
          markActiveColor(currentlyInFocus);

          // Fly to marker if valid
          if (markers[i]) {
            var m = markers[i];
            map.flyTo(m.getLatLng(), CHAPTER_ZOOM, { animate: true, duration: 2 });
          }
          break;
        }
      }
    });

    function markActiveColor(k) {
      for (var i = 0; i < markers.length; i++) {
        if (markers[i] && markers[i]._icon) {
          markers[i]._icon.className = markers[i]._icon.className.replace(' marker-active', '');
          if (i == k) {
            markers[k]._icon.className += ' marker-active';
          }
        }
      }
    }

    $('#contents').append(" \
      <div id='space-at-the-bottom'> \
        <a href='#top'>  \
          <i class='fa fa-chevron-up'></i></br> \
          <small>Top</small>  \
        </a> \
      </div> \
    ");

    $("<style>")
      .prop("type", "text/css")
      .html("\
      #narration, #title {\
        background-color: " + trySetting('_narrativeBackground', 'white') + "; \
        color: " + trySetting('_narrativeText', 'black') + "; \
      }\
      a, a:visited, a:hover {\
        color: " + trySetting('_narrativeLink', 'blue') + " \
      }\
      .in-focus {\
        background-color: " + trySetting('_narrativeActive', '#ffffff') + " \
      }")
      .appendTo("head");

    var bounds = [];
    for (i in markers) {
      if (markers[i]) {
        markers[i].addTo(map);
        markers[i]['_pixelsAbove'] = pixelsAbove[i];
        markers[i].on('click', function() {
          var pixels = parseInt($(this)[0]['_pixelsAbove']) + 5;
          $('div#contents').animate({ scrollTop: pixels + 'px' });
        });
        bounds.push(markers[i].getLatLng());
      }
    }
    if (bounds.length) {
      map.fitBounds(bounds);
    }

    $('#map, #narration, #title').css('visibility', 'visible');
    $('div.loader').css('visibility', 'hidden');

    $('div#container0').addClass("in-focus");
    $('div#contents').animate({scrollTop: '1px'});

    if (parseInt(location.hash.substr(1))) {
      var containerId = parseInt(location.hash.substr(1)) - 1;
      if ($('#container' + containerId).length) {
        $('#contents').animate({
          scrollTop: $('#container' + containerId).offset().top
        }, 1500);
      }
    }
  }

  function changeAttribution() {
    var attributionHTML = $('.leaflet-control-attribution')[0].innerHTML;
    var credit = 'View <a href="./csv/Chapters.csv" target="_blank">data</a>';
    var name = getSetting('_authorName');
    var url = getSetting('_authorURL');

    if (name && url) {
      if (url.indexOf('@') > 0) { url = 'mailto:' + url; }
      credit += ' by <a href="' + url + '">' + name + '</a> | ';
    } else if (name) {
      credit += ' by ' + name + ' | ';
    } else {
      credit += ' | ';
    }

    credit += 'View <a href="' + getSetting('_githubRepo') + '">code</a>';
    if (getSetting('_codeCredit')) credit += ' by ' + getSetting('_codeCredit');
    credit += ' with ';
    $('.leaflet-control-attribution')[0].innerHTML = credit + attributionHTML;
  }
});
