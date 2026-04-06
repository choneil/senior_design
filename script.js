// Define timeline variables
const day = 1000 * 60 * 60 * 24;
const projectStart = Date.UTC(2026, 3, 6); // April 6, 2026
const projectEnd = Date.UTC(2026, 10, 30); // Nov 30, 2026

Highcharts.ganttChart('container', {
  chart: {
    events: {
      load() {
        const xAxis = this.xAxis[0];
        document.getElementById('btn-month').addEventListener('click', () => {
          xAxis.setExtremes(projectStart, projectStart + (day * 30));
        });
        document.getElementById('btn-quarter').addEventListener('click', () => {
          xAxis.setExtremes(projectStart, projectStart + (day * 90));
        });
        document.getElementById('btn-all').addEventListener('click', () => {
          xAxis.setExtremes(projectStart, projectEnd);
        });
      }
    }
  },

  title: { text: null },

  xAxis: {
    currentDateIndicator: true,
    min: projectStart,
    max: projectEnd
  },

  navigator: {
    enabled: true,
    series: {
      type: 'gantt',
      pointPlacement: 0.5,
      pointPadding: 0.25
    }
  },
  
  scrollbar: {
    enabled: true
  },

  series: [{
    name: 'Project Timeline',
    data: [
      // -------------------------------------------------------------
      // 1. SOLDER DISPENSING / AUGER VALVE (Assigned to Chuck)
      // -------------------------------------------------------------
      { id: 'solder', name: 'Solder Dispensing (Chuck)' },
      
      { parent: 'solder', name: 'Contact suppliers (specs/pricing)', start: Date.UTC(2026, 3, 6), end: Date.UTC(2026, 3, 12) },
      { parent: 'solder', name: 'Machining tolerances, pricing', start: Date.UTC(2026, 3, 13), end: Date.UTC(2026, 3, 19) },
      { parent: 'solder', name: 'Spec screw, paste type, motor', start: Date.UTC(2026, 3, 20), end: Date.UTC(2026, 3, 26) },
      { parent: 'solder', name: 'Source all other components', start: Date.UTC(2026, 3, 27), end: Date.UTC(2026, 4, 3) },
      { parent: 'solder', name: 'Do well on finals', start: Date.UTC(2026, 4, 4), end: Date.UTC(2026, 4, 10) },
      { parent: 'solder', name: 'Draft prototype for testing', start: Date.UTC(2026, 4, 11), end: Date.UTC(2026, 4, 17) },
      { parent: 'solder', name: 'Print prototype', start: Date.UTC(2026, 4, 18), end: Date.UTC(2026, 4, 24) },
      { parent: 'solder', name: 'Design mounting/bracing', start: Date.UTC(2026, 4, 25), end: Date.UTC(2026, 4, 31) },
      { parent: 'solder', name: 'Air pressure system designed', start: Date.UTC(2026, 5, 1), end: Date.UTC(2026, 5, 7) },
      { parent: 'solder', name: 'Pressure testing chamber', start: Date.UTC(2026, 5, 8), end: Date.UTC(2026, 5, 21) },
      { parent: 'solder', name: 'Assemble mock-up of full design', start: Date.UTC(2026, 5, 22), end: Date.UTC(2026, 5, 28) },
      { parent: 'solder', name: 'Test solder paste delivery', start: Date.UTC(2026, 5, 29), end: Date.UTC(2026, 6, 5) },
      { parent: 'solder', name: 'Prototype testing', start: Date.UTC(2026, 6, 6), end: Date.UTC(2026, 6, 26) },
      { parent: 'solder', name: 'Parts assembly-ready', start: Date.UTC(2026, 6, 27), end: Date.UTC(2026, 7, 2) },
      { parent: 'solder', name: 'Assemble auger valve', start: Date.UTC(2026, 7, 3), end: Date.UTC(2026, 7, 9) },
      { parent: 'solder', name: 'Mount final design', start: Date.UTC(2026, 7, 10), end: Date.UTC(2026, 7, 16) },
      { parent: 'solder', name: 'Ensure components function', start: Date.UTC(2026, 7, 17), end: Date.UTC(2026, 7, 23) },
      { parent: 'solder', name: 'Basic solder delivery testing', start: Date.UTC(2026, 7, 24), end: Date.UTC(2026, 8, 6) },
      { parent: 'solder', name: 'Schedule Buffer', start: Date.UTC(2026, 8, 7), end: Date.UTC(2026, 9, 4) },
      { parent: 'solder', name: 'Optimize speed without sway', start: Date.UTC(2026, 9, 5), end: Date.UTC(2026, 10, 1) },
      { parent: 'solder', name: 'Finetuning (dot precision)', start: Date.UTC(2026, 10, 2), end: Date.UTC(2026, 10, 29) },
      { parent: 'solder', name: 'Reliable Operation Achieved', start: Date.UTC(2026, 10, 30), end: Date.UTC(2026, 10, 30), milestone: true },

      // -------------------------------------------------------------
      // 2. FILE HANDLING (Assigned to Andy)
      // -------------------------------------------------------------
      { id: 'file', name: 'File Handling (Andy)' },
      { parent: 'file', name: 'File Architecture & Design', start: Date.UTC(2026, 3, 6), end: Date.UTC(2026, 6, 15) },
      { parent: 'file', name: 'Parser Implementation', start: Date.UTC(2026, 6, 16), end: Date.UTC(2026, 10, 30) },

      // -------------------------------------------------------------
      // 3. COMPONENT DISPENSING (Assigned to Amar)
      // -------------------------------------------------------------
      { id: 'comp', name: 'Component Dispensing (Amar)' },
      { parent: 'comp', name: 'Dispenser Design & Prototyping', start: Date.UTC(2026, 3, 6), end: Date.UTC(2026, 6, 15) },
      { parent: 'comp', name: 'Feeder Assembly & Integration', start: Date.UTC(2026, 6, 16), end: Date.UTC(2026, 10, 30) },

      // -------------------------------------------------------------
      // 4. GANTRY / PLACEMENT (Assigned to Ainaan)
      // -------------------------------------------------------------
      { id: 'gantry', name: 'Gantry System (Ainaan)' },
      { parent: 'gantry', name: 'Mechanics & Rail Installation', start: Date.UTC(2026, 3, 6), end: Date.UTC(2026, 6, 15) },
      { parent: 'gantry', name: 'Calibration & Software Control', start: Date.UTC(2026, 6, 16), end: Date.UTC(2026, 10, 30) },

      // -------------------------------------------------------------
      // 5. OTHER SYSTEM PLACEHOLDERS (Unassigned / General)
      // -------------------------------------------------------------
      { id: 'psu', name: 'Power Supply Unit (PSU)' },
      { parent: 'psu', name: 'PSU Build & Test', start: Date.UTC(2026, 3, 6), end: Date.UTC(2026, 10, 30) },

      { id: 'board', name: 'Main Board & PCB' },
      { parent: 'board', name: 'Board Schematic & Fab', start: Date.UTC(2026, 3, 6), end: Date.UTC(2026, 10, 30) },

      { id: 'bed', name: 'Heated Bed' },
      { parent: 'bed', name: 'Thermal Systems Build', start: Date.UTC(2026, 3, 6), end: Date.UTC(2026, 10, 30) }
    ]
  }]
});