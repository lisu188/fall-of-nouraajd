package com.lisu188.fallofnouraajd;

import android.os.Bundle;

import org.libsdl.app.SDLActivity;

public final class FallOfNouraajdActivity extends SDLActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        RuntimeAssets.install(this);
        super.onCreate(savedInstanceState);
    }
}
