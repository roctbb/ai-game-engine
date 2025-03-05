const socket = io.connect();
const session_id = parseInt(location.pathname.split('/')[2]);

// Subscribe to the game session stats
socket.emit('subscribe', {
    session_id: session_id,
    mode: 'stats'
});

// Handle incoming stats data
socket.on('stats', (message) => {
    try {
        const rows = JSON.parse(message);
        let html = '<table class="table table-striped table-bordered table-hover">';

        // Function to build a table row
        const buildRow = (block, cols) => {
            let rowHtml = '';

            cols.forEach((col) => {
                // Replace empty or placeholder values with "Игрок" for headers
                const cellContent = (col === ' ' && block === 'th') ? 'Игрок' : col;

                // Add badges for specific values (e.g., status or scores)
                let cellValue = cellContent;
                if (typeof cellContent === 'string') {
                    if (cellContent.toLowerCase() === 'success') {
                        cellValue = `<span class="badge bg-success">${cellContent}</span>`;
                    } else if (cellContent.toLowerCase() === 'failed') {
                        cellValue = `<span class="badge bg-danger">${cellContent}</span>`;
                    } else if (cellContent.toLowerCase() === 'pending') {
                        cellValue = `<span class="badge bg-warning">${cellContent}</span>`;
                    }
                }

                rowHtml += `<${block}>${cellValue}</${block}>`;
            });

            return rowHtml;
        };

        // Separate header and body rows
        const headerRows = rows.filter(row => row.type === 'header');
        const bodyRows = rows.filter(row => row.type !== 'header');

        // Build table header
        if (headerRows.length > 0) {
            html += '<thead>';
            headerRows.forEach((row) => {
                html += '<tr>';
                html += buildRow('th', row.cols);
                html += '</tr>';
            });
            html += '</thead>';
        }

        // Build table body
        if (bodyRows.length > 0) {
            html += '<tbody>';
            bodyRows.forEach((row) => {
                html += '<tr>';
                html += buildRow('td', row.cols);
                html += '</tr>';
            });
            html += '</tbody>';
        }

        html += '</table>';

        // Insert the table into the DOM
        const statsElement = document.getElementById('stats');
        if (statsElement) {
            statsElement.innerHTML = html;
        } else {
            console.error('Element with id "stats" not found.');
        }
    } catch (error) {
        console.error('Error parsing or rendering stats:', error);
    }
});