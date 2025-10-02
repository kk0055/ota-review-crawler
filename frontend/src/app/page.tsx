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
import { useCrawlStatusPoller } from '@/hooks/useCrawlStatusPoller';
import {
  runCrawler,
  exportFile,
  ApiHotel,
  CrawlerOptions,
} from '@/services/crawlerApi';

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
  const [specifyDate, setSpecifyDate] = useState(true);
  const [startDate, setStartDate] = useState('2025-09-10');
  const [endDate, setEndDate] = useState('');
  const [selectedOtas, setSelectedOtas] = useState<Record<string, boolean>>({
    expedia: true,
    agoda: true,
    rakuten: false,
  });
  const [isExporting, setIsExporting] = useState(false);
  const [pollingHotelId, setPollingHotelId] = useState<number | null>(null);

  const {
    statusData,
    isLoading: isPollingLoading,
    error: pollingError,
  } = useCrawlStatusPoller({ hotelId: pollingHotelId });

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
      hotel.name.toLowerCase().includes(searchTerm.toLowerCase())
    );

    setSearchResults(filteredResults);
  }, [searchTerm, selectedHotel, allHotels]);

  const handleSelectHotel = (hotel: ApiHotel) => {
    setSelectedHotel(hotel);
    setSearchTerm(hotel.name);
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
    setPollingHotelId(null);

    const options: CrawlerOptions = {
      otas: Object.keys(selectedOtas).filter((key) => selectedOtas[key]),
      startDate: specifyDate ? startDate : null,
      endDate: specifyDate ? endDate : null,
    };

    try {
      const message = await runCrawler(selectedHotel, options);
      toast.info(message);
      setPollingHotelId(selectedHotel.id);
    } catch (error: any) {
      toast.error(`エラー: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExportFile = async () => {
    if (!selectedHotel) return;
    setIsExporting(true);

    const options: CrawlerOptions = {
      otas: Object.keys(selectedOtas).filter((key) => selectedOtas[key]),
      startDate: specifyDate ? startDate : null,
      endDate: specifyDate ? endDate : null,
    };
    try {
      await exportFile(selectedHotel, options);
    } catch (error: any) {
      toast.error(`エクスポート失敗: ${error.message}`);
    } finally {
      setIsExporting(false);
    }
  };

    const isRunCrawlerButtonDisabled =
      !selectedHotel || isLoading || isPollingLoading;

    const isExportButtonDisabled = !selectedHotel || isExporting;

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
                      <p className='font-semibold'>{hotel.name}</p>
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
            disabled={isExportButtonDisabled}
            className={`
              flex items-center justify-center w-full sm:w-auto font-bold py-3 px-8 rounded-full
              transition-all duration-300 ease-in-out
              bg-white border-2 
              ${
                isExportButtonDisabled
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
            disabled={isRunCrawlerButtonDisabled}
            className={`
              flex items-center justify-center w-full sm:w-auto font-bold py-3 px-8 rounded-full text-white 
              transition-all duration-300 ease-in-out
              ${
                isRunCrawlerButtonDisabled
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
        {pollingHotelId && selectedHotel && (
          <div className='mt-8 p-6 bg-white rounded-xl shadow-lg'>
            <h3 className='text-lg font-semibold text-slate-800 mb-4'>
              「{selectedHotel.name}」のクロール状況
            </h3>
            {isPollingLoading && !statusData.length && (
              <p>ステータスを取得中...</p>
            )}
            {pollingError && (
              <p style={{ color: 'red' }}>ステータスの取得に失敗しました。</p>
            )}

            {statusData.length > 0 && (
              <ul>
                {statusData.map((target) => (
                  <li key={target.id}>
                    <strong>{target.ota_name}:</strong>{' '}
                    {target.last_crawl_status}
                    {/* ステータスに応じたアイコンを表示すると分かりやすい */}
                    {target.last_crawl_status === 'PENDING' && ' ⏳'}
                    {target.last_crawl_status === 'SUCCESS' && ' ✅'}
                    {target.last_crawl_status === 'FAILURE' && ' ❌'}
                    <p style={{ fontSize: '0.9em', color: '#666' }}>
                      {target.last_crawl_message || '...'}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </main>
      <ToastContainer
        position='bottom-right' // 表示位置 (右下)
        autoClose={5000} // 5秒で自動的に閉じる
        hideProgressBar={false}
        newestOnTop={false}
        closeOnClick
        rtl={false}
        pauseOnFocusLoss
        draggable
        pauseOnHover
        theme='light'
      />
    </div>
  );
}
