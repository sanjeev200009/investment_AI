// src/screens/auth/OTPVerifyScreen.js
import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, Alert, StyleSheet } from 'react-native';
import { authApi } from '../../api/authApi';

export default function OTPVerifyScreen({ route, navigation }) {
  const { email } = route.params; // passed from RegisterScreen
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);

  const handleVerify = async () => {
    if (otp.length !== 6) {
      Alert.alert('Error', 'Please enter the 6-digit OTP');
      return;
    }
    setLoading(true);
    try {
      await authApi.verifyOTP(email, otp);
      Alert.alert('Success', 'Email verified! You can now log in.', 
                  [{ text: 'Login', onPress: () => navigation.replace('Login') }]);
    } catch (error) {
      const msg = error?.response?.data?.detail || 'Invalid OTP';
      Alert.alert('Error', msg);
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    try {
      await authApi.resendOTP(email);
      Alert.alert('Sent', 'New OTP sent to your email');
    } catch (e) {
      Alert.alert('Error', 'Could not resend OTP');
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Verify Your Email</Text>
      <Text style={styles.sub}>
        Enter the 6-digit code sent to{' '}
        <Text style={styles.email}>{email}</Text>
      </Text>

      <TextInput
        style={styles.input}
        value={otp}
        onChangeText={setOtp}
        keyboardType='number-pad'
        maxLength={6}
        placeholder='000000'
        textAlign='center'
      />

      <TouchableOpacity 
        style={[styles.btn, loading && styles.btnDisabled]} 
        onPress={handleVerify}
        disabled={loading}
      >
        <Text style={styles.btnText}>
          {loading ? 'Verifying...' : 'Verify OTP'}
        </Text>
      </TouchableOpacity>

      <TouchableOpacity onPress={handleResend} style={styles.resend}>
        <Text style={styles.resendText}>Did not receive it? Resend OTP</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex:1, padding:28, justifyContent:'center', backgroundColor:'#fff' },
  title: { fontSize:26, fontWeight:'bold', marginBottom:8, textAlign:'center' },
  sub: { fontSize:14, color:'#666', textAlign:'center', marginBottom:32 },
  email: { fontWeight:'bold', color:'#2F80ED' },
  input: { borderWidth:2, borderColor:'#2F80ED', borderRadius:12, padding:16, marginBottom:24, fontSize:28, letterSpacing:8, textAlign:'center' },
  btn: { backgroundColor:'#2F80ED', padding:16, borderRadius:10, alignItems:'center' },
  btnDisabled: { opacity:0.6 },
  btnText: { color:'#fff', fontSize:16, fontWeight:'bold' },
  resend: { marginTop:20, alignItems:'center' },
  resendText: { color:'#2F80ED', fontSize:14 }
});
