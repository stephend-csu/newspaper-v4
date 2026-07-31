const fs = require('fs');
const Papa = require('papaparse');

const csvText = fs.readFileSync('csv/Chapters_test.csv', 'utf8');

Papa.parse(csvText, {
    header: true,
    skipEmptyLines: true,
    complete: function(results) {
        console.log("Total rows:", results.data.length);
        let count = 0;
        results.data.forEach((row, index) => {
            if (row.Latitude && row.Longitude) {
                count++;
            }
        });
        console.log("Rows with lat/lng:", count);
        if (count === 0 && results.data.length > 0) {
            console.log("First row keys:", Object.keys(results.data[0]));
        }
    }
});
