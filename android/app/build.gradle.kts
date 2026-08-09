import org.gradle.api.GradleException
import org.gradle.api.tasks.Sync
import java.io.File

plugins {
    id("com.android.application")
}

fun requiredDirectory(propertyName: String, environmentName: String): File {
    val value = providers.gradleProperty(propertyName)
        .orElse(providers.environmentVariable(environmentName))
        .orNull
        ?.takeIf { it.isNotBlank() }
        ?: throw GradleException("Set $propertyName or $environmentName before building the Android app")
    val directory = file(value)
    if (!directory.isDirectory) {
        throw GradleException("$propertyName is not a directory: ${directory.absolutePath}")
    }
    return directory
}

val repositoryRoot = rootProject.projectDir.parentFile
val pythonPrefix = requiredDirectory("gameAndroidPythonPrefix", "GAME_ANDROID_PYTHON_PREFIX")
val dependencyPrefix = requiredDirectory("gameAndroidDependencyPrefix", "GAME_ANDROID_DEPENDENCY_PREFIX")
val sdlJavaDir = requiredDirectory("gameAndroidSdlJavaDir", "GAME_ANDROID_SDL_JAVA_DIR")

val pythonIncludeDir = File(pythonPrefix, "include").listFiles()
    ?.singleOrNull { it.isDirectory && it.name.startsWith("python3.") }
    ?: throw GradleException("Expected exactly one prefix/include/python3.* directory under ${pythonPrefix.absolutePath}")
val pythonLibrary = File(pythonPrefix, "lib").listFiles()
    ?.singleOrNull { it.isFile && it.name.startsWith("libpython3.") && it.name.endsWith(".so") }
    ?: throw GradleException("Expected exactly one libpython3.*.so under ${pythonPrefix.absolutePath}/lib")
val pythonStdlibDir = File(pythonPrefix, "lib").listFiles()
    ?.singleOrNull { it.isDirectory && it.name.startsWith("python3.") }
    ?: throw GradleException("Expected exactly one Python standard-library directory under ${pythonPrefix.absolutePath}/lib")

val generatedAssetsDir = layout.buildDirectory.dir("generated/fallOfNouraajd/assets")
val generatedJniLibsDir = layout.buildDirectory.dir("generated/fallOfNouraajd/jniLibs")

val prepareRuntimeAssets by tasks.registering(Sync::class) {
    into(generatedAssetsDir)
    from(File(repositoryRoot, "res")) {
        into("runtime")
    }
    from(File(repositoryRoot, "quest_state.py")) {
        into("runtime")
    }
    from(pythonStdlibDir) {
        into("python")
    }
}

val prepareNativeLibraries by tasks.registering(Sync::class) {
    into(generatedJniLibsDir.map { it.dir("arm64-v8a") })
    from(File(pythonPrefix, "lib")) {
        include("*.so")
    }
    from(File(dependencyPrefix, "lib")) {
        include("*.so")
    }
}

android {
    namespace = "com.lisu188.fallofnouraajd"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.lisu188.fallofnouraajd"
        minSdk = 26
        targetSdk = 37
        versionCode = 1
        versionName = "0.1.0"

        ndk {
            abiFilters += "arm64-v8a"
        }

        externalNativeBuild {
            cmake {
                arguments += listOf(
                    "-DGAME_ANDROID_PYTHON_INCLUDE_DIR=${pythonIncludeDir.absolutePath}",
                    "-DGAME_ANDROID_PYTHON_LIBRARY=${pythonLibrary.absolutePath}",
                    "-DCMAKE_PREFIX_PATH=${dependencyPrefix.absolutePath}"
                )
            }
        }
    }

    externalNativeBuild {
        cmake {
            path = File(repositoryRoot, "CMakeLists.txt")
        }
    }

    sourceSets.getByName("main") {
        java.srcDir(sdlJavaDir)
        assets.srcDir(generatedAssetsDir)
        jniLibs.srcDir(generatedJniLibsDir)
    }

    packaging {
        jniLibs {
            useLegacyPackaging = true
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

tasks.named("preBuild") {
    dependsOn(prepareRuntimeAssets)
    dependsOn(prepareNativeLibraries)
}
