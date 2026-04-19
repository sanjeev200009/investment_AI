// src/screens/StockBrowseScreen.js
import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  TouchableOpacity,
  SafeAreaView,
  StatusBar,
  FlatList,
  Modal,
  Dimensions
} from 'react-native';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useAppTheme } from '../hooks/useAppTheme';

const { height: SCREEN_HEIGHT } = Dimensions.get('window');

const MOCK_STOCKS = [
  { id: '1', symbol: 'HNB', name: 'HNB Bank PLC', price: '164.50', change: '+2.45%', isPositive: true, volume: '1.2M', isFavorite: false },
  { id: '2', symbol: 'JKH', name: 'John Keells Holdings', price: '192.00', change: '+0.75%', isPositive: true, volume: '840K', isFavorite: true },
  { id: '3', symbol: 'SAMP', name: 'Sampath Bank', price: '72.30', change: '-1.12%', isPositive: false, volume: '2.1M', isFavorite: false },
  { id: '4', symbol: 'COMB', name: 'Commercial Bank', price: '98.10', change: '-0.40%', isPositive: false, volume: '450K', isFavorite: false },
];

const CATEGORIES = ['Banking', 'Technology', 'Energy', 'Retail', 'Finance'];
const SECTORS = ['Banking', 'Energy', 'Manufacturing', 'Diversified', 'Food & Beverage'];

export default function StockBrowseScreen({ navigation }) {
  const theme = useAppTheme();
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('Banking');
  const [stocks, setStocks] = useState(MOCK_STOCKS);
  const [isFilterVisible, setIsFilterVisible] = useState(false);
  const [selectedSectors, setSelectedSectors] = useState(['Banking', 'Manufacturing']);
  const [priceRange, setPriceRange] = useState(350);

  const toggleFavorite = (id) => {
    setStocks(prev => prev.map(s => s.id === id ? { ...s, isFavorite: !s.isFavorite } : s));
  };

  const renderStockItem = ({ item }) => (
    <TouchableOpacity 
      activeOpacity={0.7}
      style={[styles.stockCard, { backgroundColor: theme.colors.surface }]}
      onPress={() => navigation.navigate('StockDetail', { stock: item })}
    >
      <View style={styles.stockInfo}>
        <View style={styles.symbolRow}>
          <Text style={[styles.stockSymbol, { color: '#42A5F5' }]}>{item.symbol}</Text>
          <Text style={[styles.stockName, { color: theme.colors.textSecondary }]}>{item.name}</Text>
        </View>
        <Text style={[styles.volumeText, { color: theme.colors.textSecondary }]}>Vol: {item.volume}</Text>
      </View>
      <View style={styles.priceContainer}>
        <Text style={[styles.priceText, { color: theme.colors.textPrimary }]}>Rs. {item.price}</Text>
        <Text style={[styles.changeText, { color: item.isPositive ? '#10B981' : '#F43F5E' }]}>{item.change}</Text>
      </View>
      <TouchableOpacity onPress={() => toggleFavorite(item.id)}>
        <MaterialIcons
          name={item.isFavorite ? "star" : "star-border"}
          size={24}
          color={item.isFavorite ? "#FBBC05" : "#8E8E93"}
        />
      </TouchableOpacity>
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: '#F2F2F7' }]}>
      <StatusBar barStyle="dark-content" />
      
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerTop}>
          <Text style={[styles.headerTitle, { color: theme.colors.textPrimary }]}>Browse Stocks</Text>
          <TouchableOpacity onPress={() => navigation.goBack()}>
            <Text style={[styles.cancelBtn, { color: '#42A5F5' }]}>Cancel</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.searchRow}>
          <View style={[styles.searchContainer, { backgroundColor: 'rgba(0,0,0,0.05)' }]}>
            <MaterialIcons name="search" size={20} color="#8E8E93" style={styles.searchIcon} />
            <TextInput
              style={styles.searchInput}
              placeholder="Search stocks, sectors..."
              value={search}
              onChangeText={setSearch}
              placeholderTextColor="#8E8E93"
            />
          </View>
          <TouchableOpacity 
            style={[styles.filterBtn, { backgroundColor: 'rgba(0,0,0,0.05)' }]}
            onPress={() => setIsFilterVisible(true)}
          >
            <MaterialIcons name="filter-list" size={24} color="#42A5F5" />
          </TouchableOpacity>
        </View>

        <ScrollView 
          horizontal 
          showsHorizontalScrollIndicator={false} 
          style={styles.categoryScroll}
          contentContainerStyle={styles.categoryContent}
        >
          {CATEGORIES.map(cat => (
            <TouchableOpacity 
              key={cat} 
              style={[
                styles.categoryChip, 
                selectedCategory === cat ? styles.activeChip : styles.inactiveChip
              ]}
              onPress={() => setSelectedCategory(cat)}
            >
              <Text style={[
                styles.categoryText, 
                selectedCategory === cat ? styles.activeChipText : styles.inactiveChipText
              ]}>
                {cat}
              </Text>
              {selectedCategory === cat && <MaterialIcons name="close" size={14} color="white" />}
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      {/* Stock List */}
      <FlatList
        data={stocks}
        renderItem={renderStockItem}
        keyExtractor={item => item.id}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
      />

      {/* Filter Modal */}
      <Modal
        visible={isFilterVisible}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setIsFilterVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <TouchableOpacity 
            style={styles.modalBlur} 
            onPress={() => setIsFilterVisible(false)} 
          />
          <View style={[styles.filterSheet, { backgroundColor: theme.colors.surface }]}>
            <View style={styles.handle} />
            
            <View style={styles.filterHeader}>
              <Text style={[styles.filterTitle, { color: theme.colors.textPrimary }]}>Filter Stocks</Text>
              <TouchableOpacity onPress={() => {
                setSelectedSectors([]);
                setPriceRange(350);
              }}>
                <Text style={[styles.resetBtn, { color: '#42A5F5' }]}>Reset</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.filterSection}>
              <Text style={styles.sectionLabel}>SECTOR</Text>
              <View style={styles.sectorContainer}>
                {SECTORS.map(sector => {
                  const isSelected = selectedSectors.includes(sector);
                  return (
                    <TouchableOpacity 
                      key={sector} 
                      style={[
                        styles.sectorChip,
                        isSelected ? styles.activeSector : styles.inactiveSector
                      ]}
                      onPress={() => {
                        setSelectedSectors(prev => 
                          prev.includes(sector) ? prev.filter(s => s !== sector) : [...prev, sector]
                        );
                      }}
                    >
                      <Text style={[
                        styles.sectorText,
                        isSelected ? styles.activeSectorText : styles.inactiveSectorText
                      ]}>
                        {sector}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            </View>

            <View style={styles.filterSection}>
              <View style={styles.rangeHeader}>
                <Text style={styles.sectionLabel}>PRICE RANGE</Text>
                <Text style={[styles.rangeValue, { color: theme.colors.textPrimary }]}>Rs. 0 - {priceRange}+</Text>
              </View>
              <View style={styles.dummySliderContainer}>
                <View style={styles.track}>
                   <View style={[styles.fill, { width: `${(priceRange / 500) * 100}%` }]} />
                   <View style={[styles.thumb, { left: `${(priceRange / 500) * 100}%` }]} />
                </View>
                <View style={styles.rangeLabels}>
                  <Text style={styles.rangeLimit}>Min Rs.0</Text>
                  <Text style={styles.rangeLimit}>Max Rs.500+</Text>
                </View>
              </View>
            </View>

            <TouchableOpacity 
              style={[styles.applyBtn, { backgroundColor: '#42A5F5' }]}
              onPress={() => setIsFilterVisible(false)}
            >
              <Text style={styles.applyBtnText}>Apply Filters</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: 8,
    backgroundColor: '#F2F2F7',
  },
  headerTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '700',
  },
  cancelBtn: {
    fontSize: 17,
    fontWeight: '500',
  },
  searchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 16,
  },
  searchContainer: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 12,
    paddingHorizontal: 12,
    height: 44,
  },
  searchIcon: {
    marginRight: 8,
  },
  searchInput: {
    flex: 1,
    fontSize: 17,
  },
  filterBtn: {
    width: 44,
    height: 44,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  categoryScroll: {
    marginBottom: 8,
  },
  categoryContent: {
    paddingRight: 16,
    gap: 8,
  },
  categoryChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    gap: 4,
  },
  activeChip: {
    backgroundColor: '#42A5F5',
  },
  inactiveChip: {
    backgroundColor: 'rgba(0,0,0,0.05)',
  },
  categoryText: {
    fontSize: 14,
    fontWeight: '600',
  },
  activeChipText: {
    color: 'white',
  },
  inactiveChipText: {
    color: '#334155',
  },
  listContent: {
    padding: 20,
    gap: 12,
  },
  stockCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderRadius: 16,
    backgroundColor: 'white',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 3,
  },
  stockInfo: {
    flex: 1,
  },
  symbolRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  stockSymbol: {
    fontSize: 18,
    fontWeight: '700',
  },
  stockName: {
    fontSize: 14,
  },
  volumeText: {
    fontSize: 12,
    marginTop: 2,
  },
  priceContainer: {
    alignItems: 'flex-end',
    marginRight: 12,
  },
  priceText: {
    fontSize: 18,
    fontWeight: '700',
  },
  changeText: {
    fontSize: 14,
    fontWeight: '500',
  },
  modalOverlay: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  modalBlur: {
    flex: 1,
  },
  filterSheet: {
    borderTopLeftRadius: 32,
    borderTopRightRadius: 32,
    paddingHorizontal: 24,
    paddingBottom: 40,
  },
  handle: {
    width: 40,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#E2E8F0',
    alignSelf: 'center',
    marginTop: 12,
    marginBottom: 24,
  },
  filterHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
  },
  filterTitle: {
    fontSize: 22,
    fontWeight: '700',
  },
  resetBtn: {
    fontSize: 16,
    fontWeight: '600',
  },
  filterSection: {
    marginBottom: 32,
  },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: '#8E8E93',
    letterSpacing: 1,
    marginBottom: 16,
  },
  sectorContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  sectorChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 12,
  },
  activeSector: {
    backgroundColor: 'rgba(66, 165, 245, 0.1)',
    borderWidth: 1,
    borderColor: '#42A5F5',
  },
  inactiveSector: {
    backgroundColor: '#F1F5F9',
  },
  sectorText: {
    fontSize: 14,
    fontWeight: '600',
  },
  activeSectorText: {
    color: '#42A5F5',
  },
  inactiveSectorText: {
    color: '#64748B',
  },
  rangeHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  rangeValue: {
    fontSize: 16,
    fontWeight: '700',
  },
  dummySliderContainer: {
    paddingHorizontal: 8,
  },
  track: {
    height: 4,
    backgroundColor: '#E2E8F0',
    borderRadius: 2,
    position: 'relative',
    marginVertical: 12,
  },
  fill: {
    height: '100%',
    backgroundColor: '#42A5F5',
    borderRadius: 2,
  },
  thumb: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: '#42A5F5',
    position: 'absolute',
    top: -10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 4,
    marginLeft: -12,
  },
  rangeLabels: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 8,
  },
  rangeLimit: {
    fontSize: 12,
    color: '#8E8E93',
  },
  applyBtn: {
    height: 56,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#42A5F5',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.3,
    shadowRadius: 16,
    elevation: 8,
  },
  applyBtnText: {
    color: 'white',
    fontSize: 18,
    fontWeight: '700',
  },
});
