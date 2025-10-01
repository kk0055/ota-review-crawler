import { useState, useEffect } from 'react';
import axios, { AxiosError } from 'axios';

type CrawlStatusValue = 'PENDING' | 'SUCCESS' | 'FAILURE' | 'NEVER_RUN';

export interface CrawlStatus {
  id: number;
  ota_name: string;
  last_crawl_status: CrawlStatusValue;
  last_crawled_at: string | null;
  last_crawl_message: string | null;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

interface UseCrawlStatusPollerProps {
  hotelName: string | null;
  interval?: number;
}

interface UseCrawlStatusPollerReturn {
  statusData: CrawlStatus[];
  isLoading: boolean;
  error: AxiosError | null;
}

export function useCrawlStatusPoller({
  hotelName,
}: UseCrawlStatusPollerProps): UseCrawlStatusPollerReturn {
  const [statusData, setStatusData] = useState<CrawlStatus[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<AxiosError | null>(null);

  useEffect(() => {
    // hotelNameがなければ何もしない
    if (!hotelName) {
      setIsLoading(false);
      return;
    }

    let isMounted = true;
    let timeoutId: NodeJS.Timeout | null = null;

    const fetchData = async () => {
      // すでにアンマウントされていたら処理を中断
      if (!isMounted) return;

      try {
        const response = await axios.get<CrawlStatus[]>(
          `${API_URL}/crawl-status/${hotelName}/`
        );

        if (isMounted) {
          const newData = response.data;
          setStatusData(newData);

          // 最新のデータですべてのクロールが完了しているかチェック
          const isPollingFinished = newData.every(
            (target) =>
              target.last_crawl_status === 'SUCCESS' ||
              target.last_crawl_status === 'FAILURE'
          );

          // まだ完了していなければ、10秒後に次のポーリングを予約
          if (!isPollingFinished) {
            timeoutId = setTimeout(fetchData, 10000); // 10秒間隔
          }
        }
      } catch (err) {
        if (isMounted) {
          if (axios.isAxiosError(err)) {
            setError(err);
          } else {
            setError(new AxiosError('An unexpected error occurred'));
          }
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    // 最初のポーリングを20秒後に開始
    timeoutId = setTimeout(fetchData, 20000);

    // クリーンアップ関数
    return () => {
      isMounted = false;
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [hotelName]); 

  return { statusData, isLoading, error };
}