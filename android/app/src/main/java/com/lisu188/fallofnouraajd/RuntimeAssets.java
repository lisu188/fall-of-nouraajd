package com.lisu188.fallofnouraajd;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.res.AssetManager;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

final class RuntimeAssets {
    private static final String RUNTIME_ASSET = "runtime";
    private static final String PYTHON_ASSET = "python";
    private static final String VERSION_FILE = ".android-runtime-version";

    private RuntimeAssets() {}

    static void install(Context context) {
        File filesDir = context.getFilesDir();
        File runtimeDir = new File(filesDir, RUNTIME_ASSET);
        File pythonDir = new File(filesDir, PYTHON_ASSET);
        File versionFile = new File(filesDir, VERSION_FILE);
        String version = Long.toString(packageVersion(context));

        if (version.equals(readVersion(versionFile)) && runtimeDir.isDirectory() && pythonDir.isDirectory()) {
            return;
        }

        deleteTree(runtimeDir);
        deleteTree(pythonDir);

        try {
            copyAssetTree(context.getAssets(), RUNTIME_ASSET, runtimeDir);
            copyAssetTree(context.getAssets(), PYTHON_ASSET, pythonDir);
            Files.writeString(versionFile.toPath(), version, StandardCharsets.UTF_8);
        } catch (IOException exception) {
            deleteTree(runtimeDir);
            deleteTree(pythonDir);
            throw new IllegalStateException("Failed to install Fall of Nouraajd runtime assets", exception);
        }
    }

    private static long packageVersion(Context context) {
        try {
            PackageInfo info = context.getPackageManager().getPackageInfo(context.getPackageName(), 0);
            return info.getLongVersionCode();
        } catch (Exception exception) {
            throw new IllegalStateException("Failed to read package version", exception);
        }
    }

    private static String readVersion(File file) {
        if (!file.isFile()) {
            return "";
        }
        try {
            return Files.readString(file.toPath(), StandardCharsets.UTF_8).trim();
        } catch (IOException ignored) {
            return "";
        }
    }

    private static void copyAssetTree(AssetManager assets, String assetPath, File destination) throws IOException {
        String[] children = assets.list(assetPath);
        if (children == null) {
            throw new IOException("Cannot enumerate asset path: " + assetPath);
        }
        if (children.length == 0) {
            File parent = destination.getParentFile();
            if (parent != null && !parent.isDirectory() && !parent.mkdirs()) {
                throw new IOException("Cannot create asset directory: " + parent);
            }
            try (InputStream input = assets.open(assetPath); FileOutputStream output = new FileOutputStream(destination)) {
                input.transferTo(output);
            }
            return;
        }

        if (!destination.isDirectory() && !destination.mkdirs()) {
            throw new IOException("Cannot create asset directory: " + destination);
        }
        for (String child : children) {
            copyAssetTree(assets, assetPath + "/" + child, new File(destination, child));
        }
    }

    private static void deleteTree(File file) {
        if (!file.exists()) {
            return;
        }
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) {
                for (File child : children) {
                    deleteTree(child);
                }
            }
        }
        if (!file.delete()) {
            throw new IllegalStateException("Cannot remove stale runtime path: " + file);
        }
    }
}
