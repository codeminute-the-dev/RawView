package io.rawview.ghidra;

import java.io.File;
import java.util.concurrent.CountDownLatch;

import ghidra.GhidraApplicationLayout;
import ghidra.framework.Application;
import ghidra.framework.HeadlessGhidraApplicationConfiguration;
import py4j.GatewayServer;

/**
 * JVM entry: initialize headless Ghidra, expose {@link GhidraBridge} on Py4J, print readiness for Python.
 *
 * <p>Args: {@code <ghidraInstallDir> <projectBaseDir> <py4jListenPort>}
 */
public final class GhidraServer {

    private GhidraServer() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 3) {
            System.err.println("usage: io.rawview.ghidra.GhidraServer <ghidraInstallDir> <projectBaseDir> <py4jPort>");
            System.exit(2);
        }
        File ghidraInstall = new File(args[0]);
        String projectBase = args[1];
        int port = Integer.parseInt(args[2].trim(), 10);

        Application.initializeApplication(
                new GhidraApplicationLayout(ghidraInstall),
                new HeadlessGhidraApplicationConfiguration());

        GhidraBridge bridge = new GhidraBridge(projectBase);
        GatewayServer server = new GatewayServer(bridge, port);
        server.start();
        System.out.println("PY4J_RAWVIEW_READY");
        System.out.flush();
        // Py4J 0.10.x: start() returns after binding; keep the JVM alive (no GatewayServer.join()).
        CountDownLatch hang = new CountDownLatch(1);
        hang.await();
    }
}
