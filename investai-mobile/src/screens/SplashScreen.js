// src/screens/SplashScreen.js
// Uses React Native's built-in Animated API for full Expo Go compatibility
import React, { useEffect, useRef, useState } from 'react';
import {
    View, Text, StyleSheet, useWindowDimensions, StatusBar,
    useColorScheme, Animated, PanResponder, TouchableOpacity, ImageBackground
} from 'react-native';
import { BlurView } from 'expo-blur';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { colors, shadows } from '../theme/theme';

const BUTTON_WIDTH = 300;
const BUTTON_HEIGHT = 70;
const THUMB_SIZE = 56;
const SWIPE_RANGE = BUTTON_WIDTH - THUMB_SIZE - 16;

const AnimatedBlurView = Animated.createAnimatedComponent(BlurView);



// ────────── Main Screen ──────────
export default function SplashScreen({ navigation }) {
    const { width, height } = useWindowDimensions();
    const scheme = useColorScheme();
    const c = colors(scheme);

    const [swiped, setSwiped] = useState(false);

    // Animations
    const fadeIn = useRef(new Animated.Value(0)).current;
    const thumbX = useRef(new Animated.Value(0)).current;
    const trackColor = useRef(new Animated.Value(0)).current;

    useEffect(() => {
        Animated.timing(fadeIn, { toValue: 1, duration: 900, useNativeDriver: true }).start();
    }, []);

    // Derived values
    const labelOpacity = thumbX.interpolate({ inputRange: [0, SWIPE_RANGE * 0.45], outputRange: [1, 0], extrapolate: 'clamp' });
    const trackBg = trackColor.interpolate({ inputRange: [0, 1], outputRange: [c.swipeBtn, scheme === 'dark' ? 'rgba(255,255,255,0.22)' : c.primaryLight] });
    const fillWidth = thumbX.interpolate({
        inputRange: [0, SWIPE_RANGE],
        outputRange: [THUMB_SIZE, THUMB_SIZE + SWIPE_RANGE],
        extrapolate: 'clamp'
    });

    const navigateNext = () => {
        navigation.navigate('Login');
    };

    const onSwipeComplete = () => {
        if (swiped) return;
        setSwiped(true);
        Animated.spring(thumbX, { toValue: SWIPE_RANGE, useNativeDriver: false }).start();
        setTimeout(navigateNext, 350);
    };

    const panResponder = PanResponder.create({
        onStartShouldSetPanResponder: () => !swiped,
        onMoveShouldSetPanResponder: () => !swiped,
        onPanResponderMove: (_, gs) => {
            const x = Math.max(0, Math.min(SWIPE_RANGE, gs.dx));
            thumbX.setValue(x);
            trackColor.setValue(x / SWIPE_RANGE);
        },
        onPanResponderRelease: (_, gs) => {
            if (gs.dx > SWIPE_RANGE * 0.78) {
                onSwipeComplete();
            } else {
                Animated.spring(thumbX, { toValue: 0, useNativeDriver: false }).start();
                Animated.timing(trackColor, { toValue: 0, duration: 250, useNativeDriver: false }).start();
            }
        },
    });

    return (
        <View style={styles.root}>
            <StatusBar barStyle={scheme === 'dark' ? 'light-content' : 'dark-content'} translucent backgroundColor="transparent" />
            <ImageBackground source={require('../../assets/splash_bg_new.png')} style={styles.bg} resizeMode="cover">



                {/* ── Main content ── */}
                <Animated.View style={[styles.content, { opacity: fadeIn }]}>
                    <View style={styles.textWrap}>
                        <Text style={[styles.title, { color: '#FFFFFF', fontSize: width > 400 ? 36 : 30 }]}>
                            The Most Trusted AI Investment Assistant
                        </Text>
                        <Text style={[styles.subtitle, { color: 'rgba(255,255,255,0.85)' }]}>
                            Navigate the markets with intelligent insights.
                        </Text>
                    </View>

                    {/* ── Swipe button ── */}
                    <View style={styles.btnCenter}>
                        <AnimatedBlurView intensity={scheme === 'dark' ? 30 : 50} tint={scheme === 'dark' ? 'dark' : 'light'} style={[styles.track, { width: BUTTON_WIDTH, backgroundColor: trackBg, overflow: 'hidden' }]}>
                            {/* Blue Fill Progress perfectly matching thumb height to stay hidden initially */}
                            <Animated.View style={{ position: 'absolute', left: 7, top: 7, height: THUMB_SIZE, width: fillWidth, borderRadius: THUMB_SIZE / 2, backgroundColor: 'rgba(25, 118, 210, 0.6)' }} />
                            <Animated.Text style={[styles.trackLabel, { opacity: labelOpacity }]}>
                                Swipe to get started
                            </Animated.Text>
                            <Animated.View style={[styles.thumbWrap, { transform: [{ translateX: thumbX }] }]} {...panResponder.panHandlers}>
                                <LinearGradient colors={scheme === 'dark' ? ['#1976D2', '#0D47A1'] : ['#FFFFFF', '#E3F0FF']} style={styles.thumb} start={[0, 0]} end={[1, 1]}>
                                    <Ionicons name="chevron-forward" size={28} color={scheme === 'dark' ? '#FFF' : c.primary} />
                                </LinearGradient>
                            </Animated.View>
                        </AnimatedBlurView>
                    </View>
                </Animated.View>



                <View style={[styles.pill, { backgroundColor: scheme === 'dark' ? 'rgba(255,255,255,0.18)' : 'rgba(3,4,94,0.1)' }]} />
            </ImageBackground>
        </View>
    );
}

const styles = StyleSheet.create({
    root: { flex: 1, width: '100%', height: '100%' },
    bg: { flex: 1, width: '100%', height: '100%' },



    content: { flex: 1, justifyContent: 'flex-end', paddingHorizontal: 28, paddingBottom: 64, zIndex: 10 },
    textWrap: { marginBottom: 44 },
    title: { fontFamily: 'Roboto_800ExtraBold', lineHeight: 42, fontWeight: '800', letterSpacing: -0.8 },
    subtitle: { fontSize: 17, marginTop: 14, fontWeight: '500', lineHeight: 26, maxWidth: 310 },

    btnCenter: { alignItems: 'center' },
    track: {
        height: BUTTON_HEIGHT,
        borderRadius: 40,
        paddingHorizontal: 7,
        justifyContent: 'center',
        overflow: 'hidden',
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.12)',
    },
    trackLabel: {
        position: 'absolute',
        left: THUMB_SIZE + 22,
        color: '#FFF',
        fontSize: 15,
        fontWeight: '700',
        letterSpacing: 0.4,
    },
    thumbWrap: { width: THUMB_SIZE, height: THUMB_SIZE },
    thumb: { flex: 1, borderRadius: THUMB_SIZE / 2, justifyContent: 'center', alignItems: 'center', elevation: 6, shadowColor: '#000', shadowOffset: { width: 0, height: 10 }, shadowOpacity: 0.28, shadowRadius: 5 },



    pill: { position: 'absolute', bottom: 14, alignSelf: 'center', width: 120, height: 5, borderRadius: 3 },
});
