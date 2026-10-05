function worksheet_to_parametricjobs(sheet, xlsx) {
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

    var jobs = [];
    rows.slice(1).forEach(function(row, index) {
        if (!row.some(has_value)) return;
        if (row.slice(headers.length).some(has_value)) {
            throw new Error(`Row ${index + 2} contains data in a column without a header.`);
        }
        var job = {};
        headers.forEach(function(header, column) {
            if (has_value(row[column])) job[header] = row[column];
        });
        jobs.push(job);
    });
    if (!jobs.length) {
        throw new Error("The first worksheet must contain at least one parametricjob row.");
    }
    return jobs;
}

class ParametricJobUpload {
    constructor(input, status, submit_button) {
        this.input = input;
        this.status = status;
        this.submit_button = submit_button;
        this.jobs = null;
        this.version = 0;
        submit_button.disabled = true;
        input.addEventListener("change", () => this.read());
    }

    async read() {
        var version = ++this.version;
        this.jobs = null;
        this.submit_button.disabled = true;
        this.status.className = "form-text text-muted";
        this.input.setCustomValidity("");
        var file = this.input.files[0];
        if (!file) {
            this.status.textContent = "Choose an Excel file to configure the parametricjobs.";
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
            this.jobs = worksheet_to_parametricjobs(workbook.Sheets[sheet_name], XLSX);
            this.status.textContent = `Loaded ${this.jobs.length} parametricjob(s) from "${sheet_name}".`;
            this.status.className = "form-text text-success";
            this.submit_button.disabled = false;
        } catch (error) {
            // A replaced file must not overwrite the latest upload's state.
            if (version !== this.version) return;
            console.error("Failed to read parametricjobs from Excel.", error);
            this.status.textContent = `Unable to load Excel file: ${error.message}`;
            this.status.className = "form-text text-danger";
            this.input.setCustomValidity(this.status.textContent);
        }
    }

    getJobs() {
        if (!this.jobs) {
            throw new Error("Load a valid Excel file before submitting the request.");
        }
        return this.jobs;
    }
}
