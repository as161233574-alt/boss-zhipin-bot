export interface CityOption {
  label: string
  value: string
  code: string
}

export const CITIES: CityOption[] = [
  { label: '全国', value: '', code: '' },
  { label: '北京', value: '北京', code: '101010100' },
  { label: '上海', value: '上海', code: '101020100' },
  { label: '广州', value: '广州', code: '101280100' },
  { label: '深圳', value: '深圳', code: '101280600' },
  { label: '杭州', value: '杭州', code: '101210100' },
  { label: '成都', value: '成都', code: '101270100' },
  { label: '南京', value: '南京', code: '101190100' },
  { label: '武汉', value: '武汉', code: '101200100' },
  { label: '西安', value: '西安', code: '101110100' },
  { label: '长沙', value: '长沙', code: '101250100' },
  { label: '重庆', value: '重庆', code: '101040100' },
  { label: '天津', value: '天津', code: '101030100' },
  { label: '苏州', value: '苏州', code: '101190400' },
  { label: '厦门', value: '厦门', code: '101230200' },
  { label: '青岛', value: '青岛', code: '101120200' },
  { label: '郑州', value: '郑州', code: '101180100' },
  { label: '合肥', value: '合肥', code: '101220100' },
  { label: '济南', value: '济南', code: '101120100' },
  { label: '大连', value: '大连', code: '101070200' },
  { label: '珠海', value: '珠海', code: '101280700' },
  { label: '佛山', value: '佛山', code: '101280800' },
  { label: '东莞', value: '东莞', code: '101281600' },
]

export function getCityCode(cityName: string): string {
  const city = CITIES.find(c => c.value === cityName)
  return city?.code ?? ''
}
