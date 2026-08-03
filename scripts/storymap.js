$(window).on('load', function() {
  var documentSettings = {};

  const CHAPTER_ZOOM = 15;

  const LIGHT_BROWN_COLOR = '#b5835a';

  var newspaperColors = {
    'NYT': '#4169e1', // Royal Blue
    'WSJ': '#6c757d', // Gray
    'SFC': '#ffd700', // Gold / Yellow
    'CAP': '#dc2626', // Red
    'UST': '#40e0d0', // Turquoise
    'EBT': '#2e7d32'  // Green
  };

  var timestamp = Date.now();
  var githubBaseUrl = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') ? 'csv/' : 'https://raw.githubusercontent.com/stephend-csu/newspaper-v4/main/csv/';

  var urlParams = new URLSearchParams(window.location.search);
  var runId = urlParams.get('id');
  
  if (!runId) {
    alert("Error: No route ID provided. Redirecting to upload page.");
    window.location.href = "/upload";
    return; // Stop execution
  }
  
  var chaptersCsv = 'Chapters_' + runId + '.csv';
  var metadataJson = 'metadata_' + runId + '.json';

  $.get(githubBaseUrl + 'Options.csv?time=' + timestamp, function(options) {
    $.get(githubBaseUrl + chaptersCsv + '?time=' + timestamp, function(chapters) {
      $.getJSON(githubBaseUrl + metadataJson + '?time=' + timestamp, function(metadata) {
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
      maxZoom: 19,
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
      var bgLight = hexToLightRgba(color, 0.18);
      styleStr += `.np-badge-${paper.toLowerCase()} { background-color: ${bgLight} !important; color: ${color} !important; border-color: ${color} !important; }\n`;
    });
    $('#newspaper-dynamic-styles').remove();
    $('<style id="newspaper-dynamic-styles">').text(styleStr).appendTo('head');
  }

  function cleanStreetAddress(fullAddr) {
    if (!fullAddr) return '';
    var streetPart = fullAddr.split(',')[0].trim();
    return streetPart.replace(/\w\S*/g, function(txt) {
      return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
    });
  }

  function initMap(options, chapters, metadata) {
    createDocumentSettings(options);
    var chapterContainerMargin = 70;
    var routeSegments = (metadata && metadata.route_segments) ? metadata.route_segments : [];

    var uniqueCities = new Set();
    chapters.forEach(function(c, idx) {
      if (idx === 0) return; // Skip depot
      if (c['Chapter']) {
        var parts = c['Chapter'].split(',');
        if (parts.length >= 2) {
          var city = parts[parts.length - 2].trim();
          if (city) {
            uniqueCities.add(city);
          }
        }
      }
    });
    
    var dynamicTitle = getSetting('_mapTitle') || '';
    if (uniqueCities.size > 0) {
      var citiesArray = Array.from(uniqueCities);
      dynamicTitle = 'Newspaper delivery route in ' + citiesArray.join(', ');
    }
    var dynamicSubtitle = getSetting('_mapSubtitle') || '';
    var urlParamsForTitle = new URLSearchParams(window.location.search);
    var runIdForTitle = urlParamsForTitle.get('id');
    if (runIdForTitle) {
      dynamicSubtitle = runIdForTitle.charAt(0).toUpperCase() + runIdForTitle.slice(1);
    }
    document.title = "Newspaper Delivery Route";
    
    if (runIdForTitle && runIdForTitle.toLowerCase() === 'admin') {
      var noteStr = ' Note: GitHub\'s CDN cache expires in 5 minutes, and browser cache is disabled.';
      if (metadata && metadata.upload_timestamp_pst) {
        var pubTimeStr = metadata.upload_timestamp_pst;
        var waitTimeStr = pubTimeStr;
        var match = pubTimeStr.match(/(.*) (\d{1,2}):(\d{2})(?::\d{2})? (AM|PM) (PST|PDT)/);
        if (match) {
            var datePart = match[1]; // e.g. "Sun, Aug 02"
            var hours = parseInt(match[2], 10);
            var mins = parseInt(match[3], 10);
            var ampm = match[4];
            
            // Reformat date part if it matches "Day, Mon DD"
            var dateMatch = datePart.match(/([a-zA-Z]+),?\s+([a-zA-Z]+)\s+(\d+)/);
            if (dateMatch) {
                var dayStr = dateMatch[1];
                if (dayStr === 'Wed') dayStr = 'Weds';
                var monthMap = {'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12};
                var monthNum = monthMap[dateMatch[2]] || dateMatch[2];
                var dayNum = parseInt(dateMatch[3], 10);
                datePart = dayStr + ' ' + monthNum + '/' + dayNum;
            }
            
            pubTimeStr = datePart + ' at ' + hours + ':' + (mins < 10 ? '0'+mins : mins) + ' ' + ampm;
            
            mins += 5;
            if (mins >= 60) {
                mins -= 60;
                hours += 1;
                if (hours == 12) {
                    ampm = (ampm === 'AM') ? 'PM' : 'AM';
                } else if (hours > 12) {
                    hours -= 12;
                }
            }
            var minStr = mins < 10 ? '0' + mins : mins;
            waitTimeStr = hours + ':' + minStr + ' ' + ampm;
        }
        var msg = 'Published at ' + pubTimeStr + '. Please wait until ' + waitTimeStr + ' for GitHub to update the map data.' + noteStr;
        $('#header').append('<div class="upload-pst-header" style="font-size:0.75rem; color:#d9534f; line-height:1.3; padding: 2px 4px;"><i class="fa fa-exclamation-triangle"></i> ' + msg + '</div>');
      } else {
        var msg = 'Please wait up to 5 minutes for GitHub to update the map data.' + noteStr;
        $('#header').append('<div class="upload-pst-header" style="font-size:0.75rem; color:#d9534f; line-height:1.3; padding: 2px 4px;"><i class="fa fa-exclamation-triangle"></i> ' + msg + '</div>');
      }
    }
    
    if (runIdForTitle) {
      $('#header-action-container').html('<a href="route_image.html?id=' + encodeURIComponent(runIdForTitle) + '" target="_blank" style="font-size:0.85rem; font-weight:bold; color:#3182ce; text-decoration:none;"><i class="fas fa-map"></i> Explore route in new tab</a>');
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

    var detectedNewspapers = new Set();
    chapters.forEach(c => {
      if (c['Newspapers']) {
        c['Newspapers'].split(/\s+/).forEach(p => {
          if (p.trim()) detectedNewspapers.add(p.trim().toUpperCase());
        });
      }
    });
    if (detectedNewspapers.size === 0) {
      ['EBT', 'WSJ', 'CAP', 'NYT', 'SFC'].forEach(p => detectedNewspapers.add(p));
    }

    updateNewspaperBadgeStyles();

    // -------------------------------------------------------------
    // DIV 1: Color Picker
    // -------------------------------------------------------------
    var colorPickerContainer = $('<div></div>', {
      id: 'container0',
      class: 'chapter-container in-focus'
    });

    function isColorTooWhite(hex) {
      if (!hex) return true;
      hex = hex.replace('#', '').trim();
      if (hex.length === 3) hex = hex.split('').map(c => c + c).join('');
      if (hex.length !== 6) return false;
      var r = parseInt(hex.substring(0, 2), 16) || 0;
      var g = parseInt(hex.substring(2, 4), 16) || 0;
      var b = parseInt(hex.substring(4, 6), 16) || 0;
      return r > 235 && g > 235 && b > 235;
    }

    var pickerCard = $('<div class="special-card-container"></div>');
    pickerCard.append('<div class="card-title"><i class="fa fa-palette"></i> Newspaper Color</div>');
    var pickerGrid = $('<div class="color-picker-grid"></div>');

    Array.from(detectedNewspapers).forEach(paper => {
      var color = newspaperColors[paper];
      if (!color || isColorTooWhite(color)) {
        color = LIGHT_BROWN_COLOR;
      }
      newspaperColors[paper] = color;
      
      var item = $('<div class="picker-item"></div>');
      item.append(`<label for="picker_${paper}">${paper}</label>`);
      var input = $(`<input type="color" id="picker_${paper}" value="${color}">`);
      input.on('input change', function() {
        var newColor = $(this).val();
        if (isColorTooWhite(newColor)) {
          newColor = LIGHT_BROWN_COLOR;
          $(this).val(newColor);
        }
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
    // DIV 2: Address Resolution Summary ("Not Routed / Included")
    // -------------------------------------------------------------
    var statsContainer = $('<div></div>', {
      id: 'container1',
      class: 'chapter-container out-focus'
    });

    var foundCount = metadata ? metadata.addresses_found : chapters.length;
    var notFoundCount = metadata ? metadata.addresses_not_found : 0;
    var notRoutedList = (metadata && metadata.not_routed_addresses) ? metadata.not_routed_addresses : [];

    var paperCounts = {};
    chapters.forEach(function(c) {
      if (c['Newspapers']) {
        c['Newspapers'].split(/\s+/).forEach(function(p) {
          var paper = p.trim().toUpperCase();
          if (paper) {
            paperCounts[paper] = (paperCounts[paper] || 0) + 1;
          }
        });
      }
    });
    
    var sortedPapers = Object.keys(paperCounts).sort(function(a, b) {
      return paperCounts[b] - paperCounts[a];
    });

    var statsCard = $('<div class="special-card-container" style="text-align: center; font-weight: bold; font-size: 1.1em; padding: 15px;"></div>');
    var foundCount = metadata ? metadata.addresses_found : chapters.length;
    statsCard.append('<div style="margin-bottom: 6px;">' + foundCount + ' addresses</div>');
    
    if (metadata && (metadata.total_drive_time || metadata.total_miles)) {
      var timeStr = metadata.total_drive_time || '';
      var milesStr = metadata.total_miles ? (metadata.total_miles + ' mi') : '';
      var metricsText = [timeStr, milesStr].filter(Boolean).join(' • ');
      if (metricsText) {
        statsCard.append('<div style="font-size: 0.95em; color: #4a5568; font-weight: 600; margin-bottom: 12px;"><i class="fa fa-clock-o" style="margin-right: 4px;"></i> Est. Drive Time: ' + metricsText + '</div>');
      }
    }
    
    var countsHtml = '<div style="font-weight: 500; font-size: 0.95em; color: #4a5568; display: flex; flex-wrap: wrap; justify-content: center; gap: 12px;">';
    sortedPapers.forEach(function(p) {
      countsHtml += '<span>' + p + ': ' + paperCounts[p] + '</span>';
    });
    countsHtml += '</div>';
    statsCard.append(countsHtml);

    statsContainer.append(statsCard);
    $('#contents').append(statsContainer);

    // -------------------------------------------------------------
    // Address Containers (containers 2, 3, ...)
    // Address 1 corresponds to container 2, Address 2 to container 3, etc.
    // -------------------------------------------------------------
    var markers = [null, null];
    var currentRouteControl = null;
    var chapterCount = 0;

    var totalAddresses = metadata && metadata.addresses_found ? metadata.addresses_found : chapters.length;
    for (var idx = 0; idx < chapters.length; idx++) {
      var c = chapters[idx];
      var containerIdx = idx + 2;
      var addressNum = idx + 1; // First address is 1.

      if (!isNaN(parseFloat(c['Latitude'])) && !isNaN(parseFloat(c['Longitude']))) {
        var lat = parseFloat(c['Latitude']);
        var lon = parseFloat(c['Longitude']);
        chapterCount += 1;

        var m = L.marker([lat, lon], {
          icon: L.ExtraMarkers.icon({
            icon: 'fa-number',
            number: c['Marker'] === 'Numbered' ? chapterCount : (c['Marker'] === 'Plain' ? '' : c['Marker']),
            markerColor: idx === 0 ? 'green' : 'cyan'
          }),
          opacity: c['Marker'] === 'Hidden' ? 0 : 0.9,
          interactive: c['Marker'] === 'Hidden' ? false : true,
        });
        m['_zoom'] = parseInt(c['Zoom']) || 19;
        markers.push(m);
      } else {
        markers.push(null);
      }

      var container = $('<div></div>', {
        id: 'container' + containerIdx,
        class: 'chapter-container out-focus'
      });

      var streetNameClean = cleanStreetAddress(c['Chapter']);
      var mapsUrl = c['Maps Link'] || (c['Chapter'] ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(c['Chapter'])}` : '#');

      var headerHtml = `<p class="chapter-header"><span class="addr-num">(${addressNum}/${totalAddresses})</span>&nbsp;&nbsp;<a href="${mapsUrl}" class="street-addr-link">${streetNameClean}</a></p>`;
      
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

      var milesToNextVal = c['Miles to Next'];
      var milesFromLastVal = idx > 0 ? chapters[idx - 1]['Miles to Next'] : null;

      var milesHtml = '';
      if (idx === 0 || (c['Description'] && c['Description'].toLowerCase().includes('start'))) {
        milesHtml = `<div class="miles-to-next"><i class="fa fa-flag-checkered"></i> Start Location</div>`;
        if (milesToNextVal) {
          milesHtml += `<div class="miles-to-next" style="margin-top: 5px; color: #718096; font-size: 1.125em;"><i class="fa fa-arrow-down" style="font-size: 0.8em; margin-right: 4px;"></i> ${parseFloat(milesToNextVal).toFixed(2)}mi</div>`;
        }
      } else {
        var toNext = (milesToNextVal && !isNaN(parseFloat(milesToNextVal))) ? parseFloat(milesToNextVal).toFixed(2) : '--';
        var fromLast = (milesFromLastVal && !isNaN(parseFloat(milesFromLastVal))) ? parseFloat(milesFromLastVal).toFixed(2) : '--';
        
        milesHtml = `
          <div class="miles-to-next" style="display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: 8px; font-size: 1.125em;">
              <span style="color: #2d3748; font-weight: 600;">${fromLast}mi</span>
              <div style="flex-grow: 0; width: 40px; height: 2px; background: #cbd5e0; position: relative;">
                  <div style="position: absolute; top: -3px; left: 50%; transform: translateX(-50%); width: 8px; height: 8px; border-radius: 50%; background: #4299e1;"></div>
              </div>
              <span style="color: #718096;">${toNext}mi</span>
          </div>
        `;
      }

      // Cuter grayscale button with downward facing triangle and flag
      var nextBtnHtml = `
      <div style="display: flex; justify-content: center; align-items: center; margin-top: 6px;">
        <div style="width: 50px; display: flex; justify-content: flex-end; margin-right: 15px;">
          <i class="fa fa-flag delivery-flag" data-state="0" style="font-size: 1.8rem; color: #cbd5e0; cursor: pointer; padding: 12px; touch-action: manipulation; -webkit-tap-highlight-color: transparent;" onclick="toggleDeliveryFlag(this)" title="Toggle delivery status"></i>
        </div>
        <button type="button" class="btn-next-address" style="margin-top: 0;" data-target-idx="${containerIdx + 1}" onclick="handleNextAddressClick(this, ${containerIdx + 1})" title="Advance to next address"><span class="cute-triangle">▾</span></button>
        <div style="width: 50px; margin-left: 15px;"></div>
      </div>`;

      container
        .append(headerHtml)
        .append(paperBadgesHtml)
        .append(milesHtml)
        .append(nextBtnHtml);

      $('#contents').append(container);
    }

    // Ensure hyperlink click always opens Google Maps
    $(document).off('click', '.street-addr-link').on('click', '.street-addr-link', function(e) {
      e.stopPropagation();
      // Let the native <a> tag click handle the navigation in the current tab
    });

    window.handleNextAddressClick = function(btnElem, targetIdx) {
      $(btnElem).addClass('pushed');
      var targetDiv = $('#container' + targetIdx);
      if (targetDiv.length) {
        var scrollPos = targetDiv.offset().top - $('#contents').offset().top + $('#contents').scrollTop() - 20;
        $('#contents').animate({
          scrollTop: scrollPos
        }, 500);
      }
    };
    
    window.toggleDeliveryFlag = function(iconElem) {
      var state = parseInt($(iconElem).attr('data-state') || '0');
      state = (state + 1) % 3;
      $(iconElem).attr('data-state', state);
      
      if (state === 1) {
        $(iconElem).css('color', '#2D11E9'); // Blue flag (1st tap)
      } else if (state === 2) {
        $(iconElem).css('color', '#FC0C04'); // Red flag (2nd tap)
      } else {
        $(iconElem).css('color', '#cbd5e0'); // Original unpressed
      }
    };

    changeAttribution();

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

      var titleOpacity = 1 - Math.min(1, currentPosition / 100);
      $('#title').css('opacity', titleOpacity);
      if (titleOpacity <= 0) {
        $('#title').css('visibility', 'hidden');
      } else {
        $('#title').css('visibility', 'visible');
      }

      for (var i = 0; i < pixelsAbove.length - 1; i++) {
        if (currentPosition >= pixelsAbove[i] && currentPosition < (pixelsAbove[i+1] - 2 * chapterContainerMargin) && currentlyInFocus != i) {
          if (i === 0) {
            location.hash = 'colors';
          } else if (i === 1) {
            location.hash = 'summary';
          } else {
            location.hash = i - 1; // Address 1 is #1, Address 2 is #2
          }

          $('.chapter-container').removeClass("in-focus").addClass("out-focus");
          $('div#container' + i).addClass("in-focus").removeClass("out-focus");

          currentlyInFocus = i;
          markActiveColor(currentlyInFocus);

          if (markers[i]) {
            var m = markers[i];
            
            if (currentRouteControl) {
              map.removeLayer(currentRouteControl);
              currentRouteControl = null;
            }
            
            var segmentIdx = i - 3;
            if (segmentIdx >= 0 && routeSegments && routeSegments[segmentIdx] && routeSegments[segmentIdx].length > 0) {
              currentRouteControl = L.polyline(routeSegments[segmentIdx], {
                color: '#60a5fa',
                opacity: 0.5,
                weight: 6
              }).addTo(map);
            }

            if (i > 2 && markers[i-1]) {
              var bounds = L.latLngBounds(markers[i-1].getLatLng(), m.getLatLng());
              map.flyToBounds(bounds, { animate: true, duration: 2, padding: [50, 50] });
            } else {
              var zoomLevel = m['_zoom'] || 18;
              map.flyTo(m.getLatLng(), zoomLevel, { animate: true, duration: 2 });
            }
          }
          break;
        }
      }
    });

    function markActiveColor(k) {
      for (var i = 0; i < markers.length; i++) {
        if (markers[i] && markers[i]._icon) {
          // Reset all marker classes to base extra-marker class logic
          markers[i]._icon.className = markers[i]._icon.className.replace(/extra-marker-circle-\w+(-(?:dark|light))?/g, '');
          markers[i]._icon.className = markers[i]._icon.className.replace(' marker-active', '');
          markers[i]._icon.style.filter = 'none';

          if (i === k) {
            // Current location: Vibrant Green
            markers[i]._icon.className += ' extra-marker-circle-green marker-active';
          } else if (i === k - 1 && i >= 2) {
            // Previous location: Light Green
            markers[i]._icon.className += ' extra-marker-circle-green-light';
            markers[i]._icon.style.filter = 'brightness(1.05)';
          } else {
            // Default location: Gray (instead of light blue)
            markers[i]._icon.className += ' extra-marker-circle-cyan';
            markers[i]._icon.style.filter = 'grayscale(100%) opacity(0.65)';
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
    markActiveColor(0);

    $('#map, #narration, #title').css('visibility', 'visible');
    $('div.loader').css('visibility', 'hidden');

    $('div#container0').addClass("in-focus");
    $('div#contents').animate({scrollTop: '1px'});

    var hashVal = location.hash.substr(1);
    if (hashVal) {
      var targetContainerId = -1;
      if (hashVal === 'colors') {
        targetContainerId = 0;
      } else if (hashVal === 'summary') {
        targetContainerId = 1;
      } else if (!isNaN(parseInt(hashVal))) {
        targetContainerId = parseInt(hashVal) + 1; // #1 -> container2
      }

      if (targetContainerId >= 0 && $('#container' + targetContainerId).length) {
        $('#contents').animate({
          scrollTop: $('#container' + targetContainerId).offset().top
        }, 1500);
      }
    }
  }

  function changeAttribution() {
    var attributionHTML = $('.leaflet-control-attribution')[0].innerHTML;
    var credit = 'View <a href="' + githubBaseUrl + chaptersCsv + '" target="_blank">data</a>';
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
