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
  hotelId: number | null;
  interval?: number;
}

interface UseCrawlStatusPollerReturn {
  statusData: CrawlStatus[];
  isLoading: boolean;
  error: AxiosError | null;
}

export function useCrawlStatusPoller({
  hotelId,
}: UseCrawlStatusPollerProps): UseCrawlStatusPollerReturn {
  const [statusData, setStatusData] = useState<CrawlStatus[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<AxiosError | null>(null);

  useEffect(() => {
    // hotelIdがなければ何もしない（状態をリセット）
    if (!hotelId) {
      setStatusData([]);
      setIsLoading(false);
      setError(null);
      return;
    }

    let isMounted = true;
    let timeoutId: NodeJS.Timeout | null = null;

    const fetchData = async () => {
      // すでにアンマウントされていたら処理を中断
      if (!isMounted) return;

      try {
        const response = await axios.get<CrawlStatus[]>(
          `${API_URL}/crawl-status/${hotelId}/`
        );

        if (isMounted) {
          const newData = response.data;
          setStatusData(newData);
          setError(null);

          // 最新のデータですべてのクロールが完了しているかチェック
          const isPollingFinished = newData.every(
            (target) =>
              target.last_crawl_status === 'SUCCESS' ||
              target.last_crawl_status === 'FAILURE'
          );

          if (isPollingFinished) {
            setIsLoading(false);
          } else {
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
          setIsLoading(false);
        }
      }
    };
    setIsLoading(true);
    // 最初のポーリングを20秒後に開始
    timeoutId = setTimeout(fetchData, 20000);

    // クリーンアップ関数
    return () => {
      isMounted = false;
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [hotelId]);

  return { statusData, isLoading, error };
}
