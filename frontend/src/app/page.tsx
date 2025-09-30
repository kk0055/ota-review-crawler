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
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import useTaskPoller from '@/hooks/useTaskPoller';

interface ApiHotel {
  id: number;
  hotel_name: string;
  ota_name: string;
  crawl_url: string;
}

// OTAの定義
const otas = [
  { id: 'expedia', name: 'Expedia' },
  { id: 'agoda', name: 'agoda' },
  { id: 'rakuten', name: '楽天トラベル' },
];
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function CrawlerAdminPage() {
  const [allHotels, setAllHotels] = useState<ApiHotel[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState<ApiHotel[]>([]);
  const [selectedHotel, setSelectedHotel] = useState<ApiHotel | null>(null);
  const [isFocused, setIsFocused] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // New states for options
  const [specifyDate, setSpecifyDate] = useState(false);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const [selectedOtas, setSelectedOtas] = useState<Record<string, boolean>>({
    expedia: true,
    agoda: true,
    rakuten: false,
  });
  const [isExporting, setIsExporting] = useState(false);
  const { pollTaskStatus } = useTaskPoller();

  useEffect(() => {
    const fetchHotels = async () => {
      try {
        const response = await axios.get<ApiHotel[]>(`${API_URL}/hotels/`);

        const data = response.data;
        setAllHotels(data);
        setSearchResults(data);
      } catch (error) {
        console.error('Failed to fetch hotels:', error);
      }
    };

    fetchHotels();
  }, []);

  useEffect(() => {
    if (selectedHotel) {
      setSearchResults([]);
      return;
    }

    const filteredResults = allHotels.filter((hotel) =>
      hotel.hotel_name.toLowerCase().includes(searchTerm.toLowerCase())
    );
    setSearchResults(filteredResults);
  }, [searchTerm, selectedHotel, allHotels]);

  const handleSelectHotel = (hotel: ApiHotel) => {
    setSelectedHotel(hotel);
    setSearchTerm(hotel.hotel_name);
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

    const payload = {
      hotel: { id: selectedHotel.id },
      options: {
        otas: Object.keys(selectedOtas).filter((key) => selectedOtas[key]),
        specifyDate: specifyDate,
        startDate: specifyDate ? startDate : null,
        endDate: specifyDate ? endDate : null,
      },
    };

    try {
      // 作成したAPIエンドポイントにPOSTリクエストを送信
      const response = await axios.post(`${API_URL}/crawlers/start/`, payload);
      const { message } = response.data;

      toast.info(message); // 「処理を開始しました」
      if (message) {
        // インポートした関数を呼び出す
        pollTaskStatus(message);
      }
      alert(
        response.data.message ||
          `${selectedHotel.hotel_name} のクローリングを開始しました！`
      );
    } catch (error: any) {
      console.error('クローラーの起動に失敗しました:', error);
      const errorMessage =
        error.response && error.response.data && error.response.data.error
          ? error.response.data.error
          : 'サーバーとの通信中にエラーが発生しました。';
      alert(`エラー: ${errorMessage}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExportFile = async () => {
    if (!selectedHotel) return;
    setIsExporting(true);

    const payload = {
      hotel: { id: selectedHotel.id },
      options: {
        otas: Object.keys(selectedOtas).filter((key) => selectedOtas[key]),
        specifyDate: specifyDate,
        startDate: specifyDate ? startDate : null,
        endDate: specifyDate ? endDate : null,
      },
    };
    try {
      const response = await axios.post(
        'http://localhost:8000/api/export/',
        payload
      );
        const { message } = response.data;

      toast.info(message);
      if (task_id) {
        pollTaskStatus(task_id);
      }
    } catch (error) {
    } finally {
      setIsExporting(false);
    }
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
                  <label className='block text-sm ...'>開始日</label>
                  <input
                    type='date'
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className='form-input w-full rounded-md border-slate-300'
                  />
                </div>
                <div>
                  <label className='block text-sm ...'>終了日</label>
                  <input
                    type='date'
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
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
