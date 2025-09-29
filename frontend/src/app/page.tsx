'use client';

import { useState, useEffect } from 'react';
import axios from 'axios'; 
import {
  Search,
  Hotel,
  CalendarDays,
  Globe,
  Bot,
  Loader2,
  X,
  FileDown,
} from 'lucide-react';

interface ApiHotel {
  id: number;
  hotel_name: string;
  ota_name: string; 
  crawl_url: string;
}

// ホテルのダミーデータ
const allHotels = [
  { id: 1, name: '帝国ホテル 東京', location: '東京都千代田区' },
  { id: 2, name: 'ザ・リッツ・カールトン東京', location: '東京都港区' },
  { id: 3, name: 'ホテルニューオータニ', location: '東京都千代田区' },
  { id: 4, name: 'マンダリン オリエンタル 東京', location: '東京都中央区' },
  { id: 5, name: 'コンラッド大阪', location: '大阪府大阪市' },
  { id: 6, name: 'ザ・リッツ・カールトン京都', location: '京都府京都市' },
];

// OTAの定義
const otas = [
  { id: 'expedia', name: 'Expedia' },
  { id: 'agoda', name: 'agoda' },
  { id: 'rakuten', name: '楽天トラベル' },
];

export default function CrawlerAdminPage() {
  const [allHotels, setAllHotels] = useState<ApiHotel[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState<ApiHotel[]>([]);
  const [selectedHotel, setSelectedHotel] = useState<ApiHotel | null>(null);
  const [isFocused, setIsFocused] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // New states for options
  const [specifyDate, setSpecifyDate] = useState(false);
  const [selectedOtas, setSelectedOtas] = useState<Record<string, boolean>>({
    expedia: true,
    agoda: true,
    rakuten: false,
  });
  const [isExporting, setIsExporting] = useState(false);
  // --- Effects and Handlers ---

  useEffect(() => {
    const fetchHotels = async () => {
      try {
    
        const response = await axios.get<ApiHotel[]>(
          'http://localhost:8000/api/hotels/'
        );

        setAllHotels(response.data);
      } catch (error) {
        console.error('Failed to fetch hotels:', error);
      }
    };

    fetchHotels();
  }, []);

  useEffect(() => {
    if (searchTerm.length > 0 && !selectedHotel) {
      // APIから取得した`allHotels`をフィルタリングする
      const filtered = allHotels.filter((hotel) =>
        hotel.hotel_name.toLowerCase().includes(searchTerm.toLowerCase())
      );
      setSearchResults(filtered);
    } else {
      setSearchResults([]);
    }
  }, [searchTerm, selectedHotel, allHotels]);

 const handleSelectHotel = (hotel: ApiHotel) => {
   setSelectedHotel(hotel);
   setSearchTerm(hotel.hotel_name); 
   setSearchResults([]);
 };

  const handleClearSelection = () => {
    setSelectedHotel(null);
    setSearchTerm('');
  };

  const handleOtaChange = (otaId: string) => {
    setSelectedOtas((prev) => ({ ...prev, [otaId]: !prev[otaId] }));
  };

  const handleRunCrawler = async () => {
    if (!selectedHotel) {
      alert('ホテルを選択してください。');
      return;
    }
    setIsLoading(true);

    const crawlerParams = {
      hotel: selectedHotel,
      options: {
        specifyDate,
        // startDate, endDate も実際にはstateで管理して渡す
        otas: Object.keys(selectedOtas).filter((key) => selectedOtas[key]),
      },
    };
    console.log('クローラー実行:', crawlerParams);

    // Django API endpoint call here...

    setTimeout(() => {
      setIsLoading(false);
      alert(`${selectedHotel.hotel_name} のクローリングを開始しました！`);
    }, 2000);
  };

  const handleExportFile = async () => {
    if (!selectedHotel) return;
    setIsExporting(true);
    console.log('ファイル出力:', { hotel: selectedHotel });
    // Django API for exporting file...
    setTimeout(() => {
      setIsExporting(false);
      alert(`${selectedHotel.hotel_name} のデータファイルを出力しました！`);
    }, 1500);
  };
  const isActionInProgress = isLoading || isExporting;
  const isButtonDisabled = !selectedHotel || isLoading;

  // --- Render ---
  return (
    <div className='min-h-screen bg-slate-50 text-slate-800'>
      <main className='max-w-3xl mx-auto p-4 sm:p-8'>
        <header className='mb-8 text-center'>
          <h1 className='text-4xl font-bold text-slate-900 mb-2'>
            Crawler Console
          </h1>
          <p className='text-slate-500'>
            ホテルとオプションを選択してクローラーを実行します。
          </p>
        </header>

        <div className='bg-white p-8 rounded-xl shadow-lg space-y-8'>
          {/* ---  ホテル検索 --- */}
          <div>
            <label
              htmlFor='hotel-search'
              className='block text-lg font-semibold text-slate-800 mb-3'
            >
              対象ホテル
            </label>
            <div className='relative'>
              <Search className='absolute left-3.5 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400' />
              <input
                id='hotel-search'
                type='text'
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                onFocus={() => setIsFocused(true)}
                onBlur={() => setTimeout(() => setIsFocused(false), 200)}
                placeholder='ホテル名を検索...'
                className='w-full pl-11 pr-10 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition'
                disabled={!!selectedHotel}
              />
              {selectedHotel && (
                <button
                  onClick={handleClearSelection}
                  className='absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600'
                >
                  <X className='w-5 h-5' />
                </button>
              )}
              {isFocused && searchResults.length > 0 && (
                <ul className='absolute z-10 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-xl max-h-60 overflow-y-auto'>
                  {searchResults.map((hotel) => (
                    <li
                      key={hotel.id}
                      onClick={() => handleSelectHotel(hotel)}
                      className='px-4 py-3 cursor-pointer hover:bg-indigo-50 transition-colors'
                    >
                      <p className='font-semibold'>{hotel.hotel_name}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* ---  期間指定 --- */}
          <div>
            <h3 className='text-lg font-semibold text-slate-800 mb-3 flex items-center'>
              <CalendarDays className='w-5 h-5 mr-2 text-indigo-500' />
              期間
            </h3>
            <div className='flex space-x-6'>
              <label className='flex items-center space-x-2 cursor-pointer'>
                <input
                  type='radio'
                  name='date-option'
                  checked={!specifyDate}
                  onChange={() => setSpecifyDate(false)}
                  className='form-radio h-4 w-4 text-indigo-600'
                />
                <span>指定しない</span>
              </label>
              <label className='flex items-center space-x-2 cursor-pointer'>
                <input
                  type='radio'
                  name='date-option'
                  checked={specifyDate}
                  onChange={() => setSpecifyDate(true)}
                  className='form-radio h-4 w-4 text-indigo-600'
                />
                <span>指定する</span>
              </label>
            </div>
            <div
              className={`transition-all duration-300 ease-in-out overflow-hidden ${
                specifyDate ? 'max-h-40 mt-4 opacity-100' : 'max-h-0 opacity-0'
              }`}
            >
              <div className='grid sm:grid-cols-2 gap-4 p-4 bg-slate-50 rounded-lg'>
                <div>
                  <label className='block text-sm font-medium text-slate-600 mb-1'>
                    開始日
                  </label>
                  <input
                    type='date'
                    className='form-input w-full rounded-md border-slate-300'
                  />
                </div>
                <div>
                  <label className='block text-sm font-medium text-slate-600 mb-1'>
                    終了日
                  </label>
                  <input
                    type='date'
                    className='form-input w-full rounded-md border-slate-300'
                  />
                </div>
              </div>
            </div>
          </div>

          {/* --- OTA選択 --- */}
          <div>
            <h3 className='text-lg font-semibold text-slate-800 mb-3 flex items-center'>
              <Globe className='w-5 h-5 mr-2 text-indigo-500' />
              対象OTA{' '}
              <span className='text-sm font-normal text-slate-500 ml-2'>
                (複数選択可)
              </span>
            </h3>
            <div className='flex flex-wrap gap-x-6 gap-y-3'>
              {otas.map((ota) => (
                <label
                  key={ota.id}
                  className='flex items-center space-x-2 cursor-pointer'
                >
                  <input
                    type='checkbox'
                    checked={selectedOtas[ota.id] || false}
                    onChange={() => handleOtaChange(ota.id)}
                    className='form-checkbox h-5 w-5 text-indigo-600 rounded'
                  />
                  <span>{ota.name}</span>
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* --- 実行ボタン --- */}
        <div className='mt-8 flex flex-col sm:flex-row justify-end items-center gap-4'>
          {/* Secondary Action: Export File */}
          <button
            onClick={handleExportFile}
            disabled={isButtonDisabled}
            className={`
              flex items-center justify-center w-full sm:w-auto font-bold py-3 px-8 rounded-full
              transition-all duration-300 ease-in-out
              bg-white border-2 
              ${
                isButtonDisabled
                  ? 'border-slate-300 text-slate-400 cursor-not-allowed'
                  : 'border-indigo-600 text-indigo-600 hover:bg-indigo-50 transform hover:scale-105'
              }
            `}
          >
            {isExporting ? (
              <>
                <Loader2 className='animate-spin -ml-1 mr-3 h-5 w-5' />
                出力中...
              </>
            ) : (
              <>
                <FileDown className='w-5 h-5 mr-2' />
                ファイル出力のみ
              </>
            )}
          </button>

          {/* Primary Action: Run Crawler */}
          <button
            onClick={handleRunCrawler}
            disabled={isButtonDisabled}
            className={`
              flex items-center justify-center w-full sm:w-auto font-bold py-3 px-8 rounded-full text-white 
              transition-all duration-300 ease-in-out
              ${
                isButtonDisabled
                  ? 'bg-slate-400 cursor-not-allowed'
                  : 'bg-indigo-600 hover:bg-indigo-700 shadow-lg hover:shadow-xl transform hover:scale-105'
              }
            `}
          >
            {isLoading ? (
              <>
                <Loader2 className='animate-spin -ml-1 mr-3 h-5 w-5' />
                実行中...
              </>
            ) : (
              <>
                <Bot className='w-5 h-5 mr-2' />
                クローラーを実行
              </>
            )}
          </button>
        </div>
      </main>
    </div>
  );
}
