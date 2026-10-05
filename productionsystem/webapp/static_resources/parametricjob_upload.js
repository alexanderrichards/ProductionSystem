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
    constructor(input, status, submit_button, summary = null) {
        this.input = input;
        this.status = status;
        this.submit_button = submit_button;
        this.summary = summary;
        this.jobs = null;
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
        this.jobs.forEach(function(job) {
            Object.keys(job).forEach(field => fields.add(field));
        });
        var heading = document.createElement("h5");
        heading.textContent = "Parametricjob preview";
        var count = document.createElement("p");
        count.textContent = `${this.jobs.length} parametricjob(s), ${fields.size} field(s). ` +
            "Defaults to the first and last jobs; choose one job number to inspect it instead. " +
            "Job numbers start at 1 and count non-empty data rows, not Excel row numbers. " +
            "Missing values are omitted from JSON; " +
            "fields empty in every job are not listed. Long values are shortened here only.";
        var controls = document.createElement("div");
        controls.className = "mb-2";
        var label = document.createElement("label");
        label.textContent = "Job number: ";
        var selection = document.createElement("input");
        selection.type = "text";
        selection.inputMode = "numeric";
        selection.placeholder = `1 to ${this.jobs.length}`;
        selection.className = "form-control form-control-sm d-inline-block w-auto mx-2";
        label.appendChild(selection);
        controls.appendChild(label);
        var choose = document.createElement("button");
        choose.type = "button";
        choose.className = "btn btn-sm btn-primary mr-2";
        choose.textContent = "Show job";
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
                number < 1 || number > this.jobs.length) {
                error.textContent = `Enter one whole job number from 1 to ${this.jobs.length}; ranges are not supported.`;
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

    renderSummaryTable(fields, wrapper, job_number = null) {
        var table = document.createElement("table");
        table.className = "table table-sm table-bordered mb-0";
        var head = table.createTHead().insertRow();
        var labels = ["Field", job_number === null ? "First job (#1)" : `Job (#${job_number})`];
        var examples = [this.jobs[job_number === null ? 0 : job_number - 1]];
        if (job_number === null && this.jobs.length > 1) {
            labels.push(`Last job (#${this.jobs.length})`);
            examples.push(this.jobs[this.jobs.length - 1]);
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
            examples.forEach(function(job) {
                var cell = row.insertCell();
                if (!Object.prototype.hasOwnProperty.call(job, field)) {
                    cell.textContent = "(omitted)";
                    cell.className = "text-muted";
                    return;
                }
                var value = JSON.stringify(job[field]);
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
        this.jobs = null;
        this.clearSummary();
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
            this.showSummary();
            this.status.textContent = `Loaded ${this.jobs.length} parametricjob(s) from "${sheet_name}".`;
            this.status.className = "form-text text-success";
            this.submit_button.disabled = false;
        } catch (error) {
            // A replaced file must not overwrite the latest upload's state.
            if (version !== this.version) return;
            this.jobs = null;
            this.clearSummary();
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
