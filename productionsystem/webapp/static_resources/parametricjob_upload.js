function worksheet_to_excel_rows(sheet, xlsx) {
    var rows = xlsx.utils.sheet_to_json(sheet, {header: 1, raw: true, defval: null, blankrows: true});
    var has_value = function(value) {
        return value !== null && value !== undefined && value !== "";
    };
    if (!rows.length || !rows[0].some(has_value)) {
        throw new Error("The first worksheet must contain a header row.");
    }

    var headers = rows[0].map(function(header) {
        return typeof header === "string" ? header.trim() : "";
    });
    var seen = new Set();
    headers.forEach(function(header, index) {
        if (!header) {
            throw new Error(`Column ${index + 1} must have a JSON field name as its header.`);
        }
        if (seen.has(header)) {
            throw new Error(`Duplicate column header: ${header}.`);
        }
        if (["__proto__", "constructor", "prototype"].includes(header)) {
            throw new Error(`Unsupported column header: ${header}.`);
        }
        seen.add(header);
    });

    var excel_rows = [];
    rows.slice(1).forEach(function(row, index) {
        if (!row.some(has_value)) return;
        if (row.slice(headers.length).some(has_value)) {
            throw new Error(`Row ${index + 2} contains data in a column without a header.`);
        }
        var excel_row = {};
        headers.forEach(function(header, column) {
            if (has_value(row[column])) excel_row[header] = row[column];
        });
        excel_rows.push(excel_row);
    });
    if (!excel_rows.length) {
        throw new Error("The first worksheet must contain at least one data row.");
    }
    return excel_rows;
}

class ParametricJobUpload {
    constructor(input, status, submit_button, summary = null) {
        this.input = input;
        this.status = status;
        this.submit_button = submit_button;
        this.summary = summary;
        this.excel_rows = null;
        this.version = 0;
        this.clearSummary();
        submit_button.disabled = true;
        input.addEventListener("change", () => this.read());
    }

    clearSummary() {
        if (!this.summary) return;
        this.summary.textContent = "";
        this.summary.hidden = true;
    }

    showSummary() {
        if (!this.summary) return;
        var fields = new Set();
        this.excel_rows.forEach(function(excel_row) {
            Object.keys(excel_row).forEach(field => fields.add(field));
        });
        var heading = document.createElement("h5");
        heading.textContent = "Excel row preview";
        var count = document.createElement("p");
        count.textContent = `${this.excel_rows.length} Excel row(s), ${fields.size} field(s). ` +
            "Defaults to the first and last rows; choose one row number to inspect it instead. " +
            "Preview row numbers start at 1 and count non-empty data rows, not Excel row numbers. " +
            "Missing values are omitted from JSON; " +
            "fields empty in every row are not listed. Long values are shortened here only.";
        var controls = document.createElement("div");
        controls.className = "mb-2";
        var label = document.createElement("label");
        label.textContent = "Row number: ";
        var selection = document.createElement("input");
        selection.type = "text";
        selection.inputMode = "numeric";
        selection.placeholder = `1 to ${this.excel_rows.length}`;
        selection.className = "form-control form-control-sm d-inline-block w-auto mx-2";
        label.appendChild(selection);
        controls.appendChild(label);
        var choose = document.createElement("button");
        choose.type = "button";
        choose.className = "btn btn-sm btn-primary mr-2";
        choose.textContent = "Show row";
        controls.appendChild(choose);
        var reset = document.createElement("button");
        reset.type = "button";
        reset.className = "btn btn-sm btn-outline-secondary";
        reset.textContent = "Show first and last";
        controls.appendChild(reset);
        var error = document.createElement("div");
        error.className = "text-danger";
        error.setAttribute("role", "alert");
        controls.appendChild(error);
        var wrapper = document.createElement("div");
        wrapper.className = "table-responsive";
        var show_selected = () => {
            var value = selection.value.trim();
            var number = Number(value);
            if (!/^[0-9]+$/.test(value) || !Number.isSafeInteger(number) ||
                number < 1 || number > this.excel_rows.length) {
                error.textContent = `Enter one whole row number from 1 to ${this.excel_rows.length}; ranges are not supported.`;
                selection.setAttribute("aria-invalid", "true");
                return;
            }
            error.textContent = "";
            selection.removeAttribute("aria-invalid");
            this.renderSummaryTable(fields, wrapper, number);
        };
        choose.addEventListener("click", show_selected);
        selection.addEventListener("keydown", function(event) {
            if (event.key === "Enter") {
                event.preventDefault();
                show_selected();
            }
        });
        reset.addEventListener("click", () => {
            selection.value = "";
            error.textContent = "";
            selection.removeAttribute("aria-invalid");
            this.renderSummaryTable(fields, wrapper);
        });
        this.renderSummaryTable(fields, wrapper);
        this.summary.appendChild(heading);
        this.summary.appendChild(count);
        this.summary.appendChild(controls);
        this.summary.appendChild(wrapper);
        this.summary.hidden = false;
    }

    renderSummaryTable(fields, wrapper, row_number = null) {
        var table = document.createElement("table");
        table.className = "table table-sm table-bordered mb-0";
        var head = table.createTHead().insertRow();
        var labels = ["Field", row_number === null ? "First row (#1)" : `Row (#${row_number})`];
        var examples = [this.excel_rows[row_number === null ? 0 : row_number - 1]];
        if (row_number === null && this.excel_rows.length > 1) {
            labels.push(`Last row (#${this.excel_rows.length})`);
            examples.push(this.excel_rows[this.excel_rows.length - 1]);
        }
        labels.forEach(function(label) {
            var cell = document.createElement("th");
            cell.scope = "col";
            cell.textContent = label;
            head.appendChild(cell);
        });
        var body = table.createTBody();
        fields.forEach(function(field) {
            var row = body.insertRow();
            var label = document.createElement("th");
            label.scope = "row";
            label.textContent = field;
            row.appendChild(label);
            examples.forEach(function(excel_row) {
                var cell = row.insertCell();
                if (!Object.prototype.hasOwnProperty.call(excel_row, field)) {
                    cell.textContent = "(omitted)";
                    cell.className = "text-muted";
                    return;
                }
                var value = JSON.stringify(excel_row[field]);
                cell.textContent = value.length > 200 ? value.slice(0, 200) + "..." : value;
                cell.style.whiteSpace = "pre-wrap";
                cell.style.overflowWrap = "anywhere";
            });
        });
        wrapper.textContent = "";
        wrapper.appendChild(table);
    }

    async read() {
        var version = ++this.version;
        this.excel_rows = null;
        this.clearSummary();
        this.submit_button.disabled = true;
        this.status.className = "form-text text-muted";
        this.input.setCustomValidity("");
        var file = this.input.files[0];
        if (!file) {
            this.status.textContent = "Choose an Excel file to load its rows.";
            return;
        }
        this.status.textContent = "Reading Excel file...";
        try {
            if (!/\.(xlsx|xls)$/i.test(file.name)) {
                throw new Error("Choose an .xlsx or .xls file.");
            }
            if (typeof XLSX === "undefined") {
                throw new Error("The Excel reader could not be loaded. Reload the page and try again.");
            }
            var buffer = await file.arrayBuffer();
            if (version !== this.version) return;
            var workbook = XLSX.read(buffer, {type: "array"});
            if (!workbook.SheetNames.length) {
                throw new Error("The workbook does not contain any worksheets.");
            }
            var sheet_name = workbook.SheetNames[0];
            this.excel_rows = worksheet_to_excel_rows(workbook.Sheets[sheet_name], XLSX);
            this.showSummary();
            this.status.textContent = `Loaded ${this.excel_rows.length} Excel row(s) from "${sheet_name}".`;
            this.status.className = "form-text text-success";
            this.submit_button.disabled = false;
        } catch (error) {
            // A replaced file must not overwrite the latest upload's state.
            if (version !== this.version) return;
            this.excel_rows = null;
            this.clearSummary();
            console.error("Failed to read Excel rows.", error);
            this.status.textContent = `Unable to load Excel file: ${error.message}`;
            this.status.className = "form-text text-danger";
            this.input.setCustomValidity(this.status.textContent);
        }
    }

    getExcelRows() {
        if (!this.excel_rows) {
            throw new Error("Load a valid Excel file before submitting the request.");
        }
        return this.excel_rows;
    }
}
