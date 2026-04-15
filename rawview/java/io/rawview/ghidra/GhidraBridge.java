package io.rawview.ghidra;

import java.io.File;
import java.io.IOException;
import java.lang.reflect.Field;
import java.util.Locale;

import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.plugin.core.analysis.AutoAnalysisManager;
import ghidra.base.project.GhidraProject;
import ghidra.framework.cmd.BackgroundCommand;
import ghidra.framework.model.DomainFile;
import ghidra.framework.model.Project;
import ghidra.framework.model.ProjectLocator;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.CommentType;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.listing.Program;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.ReferenceManager;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolIterator;
import ghidra.program.util.GhidraProgramUtilities;
import ghidra.util.exception.CancelledException;
import ghidra.util.task.TaskMonitor;

/**
 * Py4J entry-point object: import/analyze binaries and answer listing/decompiler queries.
 */
@SuppressWarnings("unused")
public class GhidraBridge {

    private final String projectBaseDir;
    private GhidraProject ghidraProject;
    private Program program;
    private DecompInterface decompiler;
    private final DecompileOptions decompileOptions = new DecompileOptions();
    /** Folder name under {@link #projectBaseDir} for the active Ghidra project (e.g. {@code rawview_…}). */
    private String currentProjectName;
    /** Absolute path of the binary last passed to {@link #openFile}; empty after {@link #openSavedProject}. */
    private String lastOpenedBinaryPath = "";
    /**
     * Set after a successful {@link #openFile} until the first {@link #flushProgramToDisk} finishes a
     * {@link GhidraProject#saveAs}. {@code importProgram} can leave a program without a real project file
     * on disk; {@link DomainFile#canSave()} may still be true, so we do not rely on it alone.
     */
    private boolean needsInitialProjectSaveAs;

    public GhidraBridge(String projectBaseDir) {
        this.projectBaseDir = projectBaseDir;
    }

    /** Health check from Python. */
    public String ping() {
        return "pong";
    }

    public synchronized String openFile(String path) throws Exception {
        closeCurrentProgramAndProject();
        File bin = new File(path);
        if (!bin.isFile()) {
            throw new IllegalArgumentException("Not a file: " + path);
        }
        String projectName = "rawview_" + System.currentTimeMillis();
        ghidraProject = GhidraProject.createProject(projectBaseDir, projectName, false);
        try {
            program = ghidraProject.importProgram(bin);
        } catch (CancelledException e) {
            throw new RuntimeException(e);
        }
        if (program == null) {
            throw new IllegalStateException("importProgram returned null");
        }
        if (decompiler != null) {
            decompiler.dispose();
        }
        decompiler = new DecompInterface();
        decompiler.setOptions(decompileOptions);
        decompiler.openProgram(program);
        currentProjectName = projectName;
        lastOpenedBinaryPath = bin.getAbsolutePath();
        needsInitialProjectSaveAs = true;
        return program.getName();
    }

    /**
     * Opens an existing on-disk Ghidra project (e.g. restored from a RawView RE session archive).
     *
     * @param projectsParentDir same semantics as {@link GhidraProject#createProject} first arg
     * @param projectFolderName directory name of the project under that parent
     * @param programFolderPath folder path inside the project (usually {@code "/"})
     * @param programDomainName domain file name of the program (see {@link #getReSessionMetaJson})
     */
    public synchronized String openSavedProject(String projectsParentDir, String projectFolderName,
            String programFolderPath, String programDomainName) throws Exception {
        closeCurrentProgramAndProject();
        try {
            ghidraProject = GhidraProject.openProject(projectsParentDir, projectFolderName, false);
        } catch (Exception e) {
            throw new IOException("openProject failed: " + e.getMessage(), e);
        }
        String folder = programFolderPath == null || programFolderPath.isEmpty() ? "/" : programFolderPath;
        program = null;
        IOException lastIo = null;
        for (String tryFolder : new String[] {folder, "/".equals(folder) ? "" : null}) {
            if (tryFolder == null) {
                continue;
            }
            try {
                program = ghidraProject.openProgram(tryFolder, programDomainName, false);
                lastIo = null;
                break;
            } catch (IOException e) {
                lastIo = e;
            }
        }
        if (program == null) {
            if (lastIo != null) {
                throw lastIo;
            }
            throw new IllegalStateException("openProgram returned null");
        }
        if (decompiler != null) {
            decompiler.dispose();
        }
        decompiler = new DecompInterface();
        decompiler.setOptions(decompileOptions);
        decompiler.openProgram(program);
        currentProjectName = projectFolderName;
        lastOpenedBinaryPath = "";
        needsInitialProjectSaveAs = false;
        return program.getName();
    }

    /** Checkpoint + save so the project folder on disk is safe to copy (RE session export). */
    public synchronized void flushProgramToDisk() throws Exception {
        ensureProgram();
        if (ghidraProject == null) {
            return;
        }
        ghidraProject.checkPoint(program);
        /*
         * importProgram() can leave a Program whose DomainFile has no on-disk location yet;
         * GhidraProject.save() then throws ReadOnlyException ("Location does not exist for a save
         * operation!"). Some Ghidra builds report canSave()==true anyway, so after openFile we always
         * saveAs once, then use save() / canSave checks thereafter.
         */
        if (needsInitialProjectSaveAs) {
            ghidraProject.saveAs(program, "/", safeProgramDomainName(program), true);
            needsInitialProjectSaveAs = false;
            return;
        }
        DomainFile df = program.getDomainFile();
        if (df == null || !df.canSave()) {
            ghidraProject.saveAs(program, "/", safeProgramDomainName(program), true);
            return;
        }
        try {
            ghidraProject.save(program);
        } catch (Exception e) {
            if (isMissingDomainSaveLocation(e)) {
                ghidraProject.saveAs(program, "/", safeProgramDomainName(program), true);
            } else {
                throw e;
            }
        }
    }

    /** Sanitized name for {@link GhidraProject#saveAs} under the project root folder. */
    private static String safeProgramDomainName(Program p) {
        String n = p.getName();
        if (n == null) {
            n = "";
        }
        n = n.trim();
        if (n.isEmpty()) {
            n = "program";
        }
        StringBuilder sb = new StringBuilder(n.length());
        for (int i = 0; i < n.length(); i++) {
            char c = n.charAt(i);
            if (c <= ' ' || c == '\\' || c == '/' || c == ':' || c == '*' || c == '?' || c == '"'
                    || c == '<' || c == '>' || c == '|') {
                sb.append('_');
            } else {
                sb.append(c);
            }
        }
        String out = sb.toString();
        if (out.length() > 200) {
            out = out.substring(0, 200);
        }
        return out;
    }

    private static boolean isMissingDomainSaveLocation(Throwable e) {
        for (Throwable t = e; t != null; t = t.getCause()) {
            String msg = t.getMessage();
            if (msg != null && msg.contains("Location does not exist")) {
                return true;
            }
        }
        return false;
    }

    /** JSON for Python RE session pack: project folder, domain path, original binary path, Ghidra parent dir. */
    public synchronized String getReSessionMetaJson() throws Exception {
        if (program == null || currentProjectName == null || currentProjectName.isEmpty()) {
            return "{}";
        }
        DomainFile df = program.getDomainFile();
        ghidra.framework.model.DomainFolder parent = df.getParent();
        String folderPath = "/";
        if (parent != null) {
            String pn = parent.getPathname();
            if (pn != null && !pn.isEmpty()) {
                folderPath = pn.startsWith("/") ? pn : "/" + pn;
            }
        }
        /*
         * Python must zip the real on-disk project directory. Ghidra may not materialize
         * projectBaseDir/projectName until saveAs; ProjectLocator is authoritative once the
         * project exists (and matches what flushProgramToDisk wrote).
         */
        String projectFolderOnDisk = "";
        try {
            if (ghidraProject != null) {
                Project pj = ghidraProject.getProject();
                if (pj != null) {
                    ProjectLocator loc = pj.getProjectLocator();
                    if (loc != null) {
                        File pd = loc.getProjectDir();
                        if (pd != null) {
                            projectFolderOnDisk = pd.getAbsolutePath();
                        }
                    }
                }
            }
        } catch (Exception ignored) {
        }
        if (projectFolderOnDisk.isEmpty()) {
            projectFolderOnDisk = new File(projectBaseDir, currentProjectName).getAbsolutePath();
        }
        return "{\"projectName\":\"" + escapeJson(currentProjectName) + "\",\"projectsParent\":\""
                + escapeJson(projectBaseDir) + "\",\"projectFolderOnDisk\":\""
                + escapeJson(projectFolderOnDisk) + "\",\"programFolder\":\"" + escapeJson(folderPath)
                + "\",\"programDomainName\":\"" + escapeJson(df.getName()) + "\",\"originalBinary\":\""
                + escapeJson(lastOpenedBinaryPath != null ? lastOpenedBinaryPath : "") + "\"}";
    }

    public synchronized void runAutoAnalysis() throws Exception {
        ensureProgram();
        /*
         * GhidraProject.importProgram() leaves an open "Batch Processing" transaction; commit it
         * before analysis (Headless uses ProgramLoader + DefaultProject instead).
         */
        if (ghidraProject != null) {
            ghidraProject.checkPoint(program);
        }
        /*
         * Mirror HeadlessAnalyzer.analyzeProgram(): explicit "Analysis" transaction, then dispose
         * the manager (GhidraProject.analyze() does not do either).
         */
        AutoAnalysisManager mgr = AutoAnalysisManager.getAnalysisManager(program);
        mgr.initializeOptions();
        int txId = program.startTransaction("Analysis");
        File progressFile = new File(projectBaseDir, ".rawview_analysis_progress.json");
        AnalysisProgressMonitor analysisMonitor = new AnalysisProgressMonitor(progressFile, () -> readActiveCommandDetail(mgr));
        try {
            mgr.reAnalyzeAll(null);
            mgr.startAnalysis(analysisMonitor);
            GhidraProgramUtilities.markProgramAnalyzed(program);
        } finally {
            program.endTransaction(txId, true);
            analysisMonitor.clearFile();
        }
        mgr.dispose();
    }

    /**
     * Reads the active {@link BackgroundCommand}'s {@code getName()} / {@code getStatusMsg()} via the same
     * private fields Ghidra's UI uses. {@code getStatusMsg()} is where many analyzers put the current function
     * or address. Invoked only from {@link AnalysisProgressMonitor#flush} (Ghidra-driven), not on a timer.
     */
    private static String readActiveCommandDetail(AutoAnalysisManager mgr) {
        try {
            Field af = AutoAnalysisManager.class.getDeclaredField("activeTask");
            af.setAccessible(true);
            Object wrapper = af.get(mgr);
            if (wrapper == null) {
                return null;
            }
            Field tf = wrapper.getClass().getDeclaredField("task");
            tf.setAccessible(true);
            Object cmd = tf.get(wrapper);
            if (!(cmd instanceof BackgroundCommand)) {
                return null;
            }
            BackgroundCommand<?> bc = (BackgroundCommand<?>) cmd;
            String name = bc.getName();
            if (name == null) {
                name = "";
            }
            String st = bc.getStatusMsg();
            if (st != null) {
                st = st.trim();
            } else {
                st = "";
            }
            if (!st.isEmpty()) {
                if (!name.isEmpty() && !st.contains(name)) {
                    return name + " \u2014 " + st;
                }
                return st;
            }
            return name.isEmpty() ? null : name;
        } catch (ReflectiveOperationException | ClassCastException ignored) {
        }
        return null;
    }

    /** JSON array of objects {@code {name,address}} for stable Py4J transfer. */
    public synchronized String listFunctionsJson() throws Exception {
        ensureProgram();
        FunctionManager fm = program.getFunctionManager();
        FunctionIterator it = fm.getFunctions(true);
        StringBuilder sb = new StringBuilder("[");
        boolean first = true;
        while (it.hasNext()) {
            Function f = it.next();
            if (!first) {
                sb.append(',');
            }
            first = false;
            sb.append("{\"name\":\"").append(escapeJson(f.getName())).append("\",");
            sb.append("\"address\":\"").append(escapeJson(f.getEntryPoint().toString())).append("\"}");
        }
        sb.append(']');
        return sb.toString();
    }

    public synchronized String decompileFunction(String addressText) throws Exception {
        ensureProgram();
        Function f = resolveFunction(addressText);
        if (f == null) {
            return "// No function at " + addressText;
        }
        DecompileResults results = decompiler.decompileFunction(f, 120, TaskMonitor.DUMMY);
        if (results == null || !results.decompileCompleted()) {
            String err = results != null ? results.getErrorMessage() : "null results";
            return "// Decompile failed: " + err;
        }
        if (results.getDecompiledFunction() == null) {
            return "// No decompiled output";
        }
        return results.getDecompiledFunction().getC();
    }

    public synchronized String getDisassembly(String addressText, int maxInstructions) throws Exception {
        ensureProgram();
        Address start = program.getAddressFactory().getAddress(addressText.trim());
        if (start == null) {
            return "Invalid address: " + addressText;
        }
        int cap = Math.max(1, Math.min(maxInstructions, 5000));
        Listing listing = program.getListing();
        StringBuilder sb = new StringBuilder();
        InstructionIterator ii = listing.getInstructions(start, true);
        int n = 0;
        while (ii.hasNext() && n < cap) {
            Instruction ins = ii.next();
            sb.append(ins.getAddressString(true, false)).append('\t').append(ins.toString()).append('\n');
            n++;
        }
        return sb.toString();
    }

    /**
     * Tab-separated hex dump for UI: {@code address TAB hex-spaces TAB ascii} per row; lines starting with
     * {@code #} are metadata / column headers. Mapped bytes only.
     *
     * @param maxBytes capped (1..65536)
     * @param bytesPerLine columns (1..64), with an extra gap after the first half when ≥ 8
     */
    public synchronized String getHexDumpText(String addressText, int maxBytes, int bytesPerLine) throws Exception {
        ensureProgram();
        Address addr = program.getAddressFactory().getAddress(addressText.trim());
        if (addr == null) {
            return "Invalid address: " + addressText;
        }
        int bpl = Math.max(1, Math.min(bytesPerLine, 64));
        int cap = Math.max(1, Math.min(maxBytes, 65536));
        Memory mem = program.getMemory();
        byte[] data = new byte[cap];
        int got;
        try {
            got = mem.getBytes(addr, data);
        } catch (Exception e) {
            return "Could not read bytes at " + addr + ": " + e.getMessage();
        }
        if (got <= 0) {
            return "(no bytes read at " + addr + " - unmapped or protected?)";
        }
        StringBuilder out = new StringBuilder(Math.min(got, cap) * 5 + 128);
        out.append("# base\t").append(addr.toString()).append("\tbytes=").append(got).append("\tcolumns=").append(bpl)
                .append("\n");
        out.append("#\n");
        StringBuilder hexIdx = new StringBuilder();
        for (int c = 0; c < bpl; c++) {
            if (c == bpl / 2 && bpl >= 8) {
                hexIdx.append("  ");
            }
            hexIdx.append(String.format(Locale.US, "%02X", c));
            if (c + 1 < bpl) {
                hexIdx.append(' ');
            }
        }
        StringBuilder asciiIdx = new StringBuilder(bpl);
        for (int c = 0; c < bpl; c++) {
            int v = c % 16;
            asciiIdx.append(v < 10 ? (char) ('0' + v) : (char) ('A' + v - 10));
        }
        out.append("# offset\t").append(hexIdx).append("\t").append(asciiIdx).append("\n");
        for (int off = 0; off < got; off += bpl) {
            int n = Math.min(bpl, got - off);
            Address rowAddr = addr.addWrap(off);
            out.append(rowAddr.toString()).append('\t');
            for (int i = 0; i < n; i++) {
                if (i == bpl / 2 && bpl >= 8) {
                    out.append("  ");
                }
                int b = data[off + i] & 0xff;
                out.append(String.format(Locale.US, "%02X", b));
                if (i + 1 < n) {
                    out.append(' ');
                }
            }
            for (int i = n; i < bpl; i++) {
                if (i == bpl / 2 && bpl >= 8) {
                    out.append("  ");
                }
                out.append("  ");
                if (i + 1 < bpl) {
                    out.append(' ');
                }
            }
            out.append('\t');
            for (int i = 0; i < n; i++) {
                int b = data[off + i] & 0xff;
                char ch = (b >= 32 && b < 127) ? (char) b : '.';
                out.append(ch);
            }
            for (int i = n; i < bpl; i++) {
                out.append(' ');
            }
            out.append('\n');
        }
        return out.toString();
    }

    /** Move {@code addressText} forward/back in the default space (wrap). Empty string if invalid. */
    public synchronized String advanceProgramAddress(String addressText, long deltaBytes) throws Exception {
        ensureProgram();
        Address a = program.getAddressFactory().getAddress(addressText.trim());
        if (a == null) {
            return "";
        }
        Address n = a.addWrap(deltaBytes);
        return n != null ? n.toString() : "";
    }

    /** JSON array of {@code {address,value}} for defined string data. */
    public synchronized String getStringsJson() throws Exception {
        ensureProgram();
        Listing listing = program.getListing();
        StringBuilder sb = new StringBuilder("[");
        boolean first = true;
        DataIterator dit = listing.getDefinedData(true);
        while (dit.hasNext()) {
            Data d = dit.next();
            if (!d.hasStringValue()) {
                continue;
            }
            if (!first) {
                sb.append(',');
            }
            first = false;
            String val = d.getDefaultValueRepresentation();
            sb.append("{\"address\":\"").append(escapeJson(d.getAddressString(true, false))).append("\",");
            sb.append("\"value\":\"").append(escapeJson(val)).append("\"}");
        }
        sb.append(']');
        return sb.toString();
    }

    /** JSON array of {@code {library,name,address}} for external symbols. */
    public synchronized String getImportsJson() throws Exception {
        ensureProgram();
        StringBuilder sb = new StringBuilder("[");
        boolean first = true;
        SymbolIterator it = program.getSymbolTable().getAllSymbols(true);
        while (it.hasNext()) {
            Symbol s = it.next();
            if (!s.isExternal()) {
                continue;
            }
            if (!first) {
                sb.append(',');
            }
            first = false;
            String lib = s.getParentNamespace() != null ? s.getParentNamespace().getName() : "";
            sb.append("{\"library\":\"").append(escapeJson(lib)).append("\",");
            sb.append("\"name\":\"").append(escapeJson(s.getName())).append("\",");
            sb.append("\"address\":\"").append(escapeJson(s.getAddress().toString())).append("\"}");
        }
        sb.append(']');
        return sb.toString();
    }

    /** JSON array of {@code {name,address}} for primary symbols at image base / common entry labels (MVP). */
    public synchronized String getExportsJson() throws Exception {
        ensureProgram();
        StringBuilder sb = new StringBuilder("[");
        boolean first = true;
        SymbolIterator it = program.getSymbolTable().getAllSymbols(true);
        int cap = 0;
        while (it.hasNext() && cap < 2000) {
            Symbol s = it.next();
            if (!s.isPrimary()) {
                continue;
            }
            if (s.isExternal()) {
                continue;
            }
            if (!first) {
                sb.append(',');
            }
            first = false;
            cap++;
            sb.append("{\"name\":\"").append(escapeJson(s.getName())).append("\",");
            sb.append("\"address\":\"").append(escapeJson(s.getAddress().toString())).append("\"}");
        }
        sb.append(']');
        return sb.toString();
    }

    /**
     * JSON array of {@code {name,address}} for defined non-external symbols (includes labels;
     * broader than {@link #getExportsJson()} which keeps primary symbols only). Capped for UI transfer.
     */
    public synchronized String getSymbolsJson() throws Exception {
        ensureProgram();
        StringBuilder sb = new StringBuilder("[");
        boolean first = true;
        SymbolIterator it = program.getSymbolTable().getAllSymbols(true);
        int cap = 0;
        while (it.hasNext() && cap < 5000) {
            Symbol s = it.next();
            if (s.isExternal()) {
                continue;
            }
            if (!first) {
                sb.append(',');
            }
            first = false;
            cap++;
            sb.append("{\"name\":\"").append(escapeJson(s.getName())).append("\",");
            sb.append("\"address\":\"").append(escapeJson(s.getAddress().toString())).append("\"}");
        }
        sb.append(']');
        return sb.toString();
    }

    /** JSON array of {@code {address,name}} entry-like symbols (MVP: primary at image base + named entry). */
    public synchronized String getEntryPointsJson() throws Exception {
        ensureProgram();
        StringBuilder sb = new StringBuilder("[");
        Address base = program.getImageBase();
        if (base != null) {
            Symbol s = program.getSymbolTable().getPrimarySymbol(base);
            if (s != null) {
                sb.append("{\"address\":\"").append(escapeJson(base.toString())).append("\",");
                sb.append("\"name\":\"").append(escapeJson(s.getName())).append("\"}");
            }
        }
        sb.append(']');
        return sb.toString();
    }

    /** JSON array of {@code {fromAddress,toAddress,type}} references to {@code addressText}. */
    public synchronized String getXrefsToJson(String addressText) throws Exception {
        ensureProgram();
        Address addr = program.getAddressFactory().getAddress(addressText.trim());
        if (addr == null) {
            return "[]";
        }
        ReferenceManager rm = program.getReferenceManager();
        StringBuilder sb = new StringBuilder("[");
        boolean first = true;
        ReferenceIterator toIt = rm.getReferencesTo(addr);
        while (toIt != null && toIt.hasNext()) {
            Reference ref = toIt.next();
            if (!first) {
                sb.append(',');
            }
            first = false;
            sb.append("{\"fromAddress\":\"").append(escapeJson(ref.getFromAddress().toString())).append("\",");
            sb.append("\"toAddress\":\"").append(escapeJson(ref.getToAddress().toString())).append("\",");
            sb.append("\"type\":\"").append(escapeJson(ref.getReferenceType().toString())).append("\"}");
        }
        sb.append(']');
        return sb.toString();
    }

    /** JSON array of {@code {fromAddress,toAddress,type}} references from {@code addressText}. */
    public synchronized String getXrefsFromJson(String addressText) throws Exception {
        ensureProgram();
        Address addr = program.getAddressFactory().getAddress(addressText.trim());
        if (addr == null) {
            return "[]";
        }
        ReferenceManager rm = program.getReferenceManager();
        StringBuilder sb = new StringBuilder("[");
        boolean first = true;
        Reference[] fromRefs = rm.getReferencesFrom(addr);
        if (fromRefs != null) {
            for (Reference ref : fromRefs) {
                if (!first) {
                    sb.append(',');
                }
                first = false;
                sb.append("{\"fromAddress\":\"").append(escapeJson(ref.getFromAddress().toString())).append("\",");
                sb.append("\"toAddress\":\"").append(escapeJson(ref.getToAddress().toString())).append("\",");
                sb.append("\"type\":\"").append(escapeJson(ref.getReferenceType().toString())).append("\"}");
            }
        }
        sb.append(']');
        return sb.toString();
    }

    public synchronized String renameFunction(String addressText, String newName) throws Exception {
        ensureProgram();
        Function f = resolveFunction(addressText);
        if (f == null) {
            return "{\"error\":\"no_function_at_address\"}";
        }
        f.setName(newName, SourceType.USER_DEFINED);
        return "{\"ok\":true,\"address\":\"" + escapeJson(f.getEntryPoint().toString()) + "\",\"name\":\""
                + escapeJson(newName) + "\"}";
    }

    public synchronized String setComment(String addressText, String text) throws Exception {
        ensureProgram();
        Address addr = program.getAddressFactory().getAddress(addressText.trim());
        if (addr == null) {
            return "{\"error\":\"invalid_address\"}";
        }
        program.getListing().setComment(addr, CommentType.EOL, text);
        return "{\"ok\":true}";
    }

    /** Space-separated hex bytes, e.g. {@code "48 89 E5"}. Returns first match address or empty. */
    public synchronized String searchBytesJson(String hexPattern) throws Exception {
        ensureProgram();
        String[] parts = hexPattern.trim().split("\\s+");
        if (parts.length == 0 || parts[0].isEmpty()) {
            return "{\"matches\":[]}";
        }
        byte[] pat = new byte[parts.length];
        for (int i = 0; i < parts.length; i++) {
            pat[i] = (byte) Integer.parseInt(parts[i], 16);
        }
        Memory mem = program.getMemory();
        Address start = program.getMinAddress();
        Address found = mem.findBytes(start, pat, null, true, TaskMonitor.DUMMY);
        if (found == null) {
            return "{\"matches\":[]}";
        }
        return "{\"matches\":[{\"address\":\"" + escapeJson(found.toString()) + "\"}]}";
    }

    /** JSON object describing bytes or instruction at address (MVP). */
    public synchronized String getDataAtJson(String addressText) throws Exception {
        ensureProgram();
        Address addr = program.getAddressFactory().getAddress(addressText.trim());
        if (addr == null) {
            return "{\"error\":\"invalid_address\"}";
        }
        Listing listing = program.getListing();
        Data d = listing.getDefinedDataAt(addr);
        if (d != null) {
            return "{\"kind\":\"data\",\"address\":\"" + escapeJson(addr.toString()) + "\",\"representation\":\""
                    + escapeJson(d.getDefaultValueRepresentation()) + "\"}";
        }
        Instruction ins = listing.getInstructionAt(addr);
        if (ins != null) {
            return "{\"kind\":\"instruction\",\"address\":\"" + escapeJson(addr.toString()) + "\",\"mnemonic\":\""
                    + escapeJson(ins.getMnemonicString()) + "\"}";
        }
        return "{\"kind\":\"unknown\",\"address\":\"" + escapeJson(addr.toString()) + "\"}";
    }

    /** Placeholder CFG as JSON for native graph rendering. */
    public synchronized String getControlFlowGraphJson(String addressText) throws Exception {
        ensureProgram();
        Function f = resolveFunction(addressText);
        if (f == null) {
            return "{\"error\":\"no_function\",\"nodes\":[],\"edges\":[]}";
        }
        return "{\"function\":\"" + escapeJson(f.getName()) + "\",\"entry\":\""
                + escapeJson(f.getEntryPoint().toString()) + "\",\"nodes\":[],\"edges\":[],\"note\":\"MVP_placeholder\"}";
    }

    public synchronized String renameVariable(String functionAddress, String oldName, String newName) throws Exception {
        return "{\"error\":\"not_implemented\",\"hint\":\"Decompiler variable rename requires HighVariable API wiring\"}";
    }

    public synchronized String createStruct(String addressText, String structDefinition) throws Exception {
        return "{\"error\":\"not_implemented\"}";
    }

    public synchronized String setFunctionSignature(String addressText, String signature) throws Exception {
        return "{\"error\":\"not_implemented\"}";
    }

    public synchronized void closeAll() {
        closeCurrentProgramAndProject();
    }

    /** Image base address string for navigation when no functions/exports are listed yet. */
    public synchronized String getImageBaseAddress() throws Exception {
        ensureProgram();
        Address b = program.getImageBase();
        return b != null ? b.toString() : "";
    }

    // -------------------------------------------------------------------------

    private void ensureProgram() {
        if (program == null) {
            throw new IllegalStateException("No program loaded; call openFile first");
        }
    }

    private static String escapeJson(String s) {
        if (s == null) {
            return "";
        }
        StringBuilder b = new StringBuilder(s.length() + 16);
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '\\':
                    b.append("\\\\");
                    break;
                case '"':
                    b.append("\\\"");
                    break;
                case '\n':
                    b.append("\\n");
                    break;
                case '\r':
                    b.append("\\r");
                    break;
                case '\t':
                    b.append("\\t");
                    break;
                default:
                    if (c < 0x20) {
                        b.append(String.format("\\u%04x", (int) c));
                    } else {
                        b.append(c);
                    }
                    break;
            }
        }
        return b.toString();
    }

    private Function resolveFunction(String addressText) {
        Address addr = program.getAddressFactory().getAddress(addressText.trim());
        if (addr == null) {
            return null;
        }
        FunctionManager fm = program.getFunctionManager();
        Function f = fm.getFunctionAt(addr);
        if (f != null) {
            return f;
        }
        return fm.getFunctionContaining(addr);
    }

    private void closeCurrentProgramAndProject() {
        needsInitialProjectSaveAs = false;
        if (decompiler != null) {
            try {
                decompiler.dispose();
            } catch (Exception ignored) {
            }
            decompiler = null;
        }
        if (ghidraProject != null) {
            try {
                ghidraProject.close();
            } catch (Exception ignored) {
            }
            ghidraProject = null;
        }
        program = null;
        currentProjectName = null;
    }
}
