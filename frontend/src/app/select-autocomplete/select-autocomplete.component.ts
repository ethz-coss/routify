import { ChangeDetectorRef, Component, ElementRef, Input, OnDestroy, AfterViewInit } from '@angular/core';
import { CommonModule } from '@angular/common';
// import custom components
import { NgSelectModule } from '@ng-select/ng-select';
import { FormsModule } from '@angular/forms';
import { Observable, of, Subject } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import { AutoCompleteService, Feature } from '../../autocomplete.service';

@Component({
  selector: 'app-select-autocomplete',
  standalone: true,
  imports: [
    CommonModule,
    NgSelectModule,
    FormsModule
  ],
  templateUrl: './select-autocomplete.component.html',
  styleUrl: './select-autocomplete.component.css'
})
export class SelectAutocompleteComponent implements OnDestroy, AfterViewInit {
  @Input() placeholder: string = "";
  items: Observable<Feature[]> | undefined;
  selectedItem: number = -1;
  private searchSubject = new Subject<string>();
  public value : Feature | null = null;

  constructor(private dataService: AutoCompleteService, private cdr: ChangeDetectorRef, private elementRef: ElementRef) {
    this.setupTypeahead();
  }

  private setupTypeahead(): void {
    this.searchSubject.pipe(
      debounceTime(300),
      distinctUntilChanged()
    ).subscribe(async (term) => {
      this.items = await this.dataService.getFeatures(term);
      // Use markForCheck instead of detectChanges to avoid the error
      this.cdr.markForCheck();
    });
  }

  public setValue(value: Feature): void {
    this.value = value;
    // Ensure items array contains the new value for proper display
    this.items = of([value]); // of converts Feature[] to Observable<Feature[]>
    this.selectedItem = 0;
    // Force change detection to ensure UI updates
    this.cdr.detectChanges();
    // Force a refresh of the ng-select display
    this.forceRefresh();
  }

  // Force refresh the ng-select display
  private forceRefresh(): void {
    // Temporarily clear items and restore to force ng-select to refresh
    const currentItems = this.items;
    this.items = undefined;
    setTimeout(() => {
      this.items = currentItems;
      this.cdr.detectChanges();
    }, 10);
  }

  //Select and unselect the field to trigger the correct update
  public updateField() {
    // Instead of manually triggering focus/blur, we'll use a different approach
    // that doesn't interfere with Angular's change detection
    this.cdr.markForCheck();
  }

  public resetField() {
    this.value = null;
    this.items = undefined;
    this.selectedItem = -1;
    // Force change detection to ensure UI updates
    this.cdr.detectChanges();
    // Force a refresh of the ng-select display
    this.forceRefresh();
  }

  public onSelectionChanged(event: any): void {
    this.value = event;
    // Update selectedItem to maintain consistency
    if (event && this.items) {
      this.items.subscribe(items => {
        if (items && items.length > 0) {
          const index = items.findIndex(item => item.id === event.id);
          this.selectedItem = index >= 0 ? index : -1;
        }
      });
    } else {
      this.selectedItem = -1;
    }
    // Force change detection to ensure UI updates
    this.cdr.detectChanges();
  }

  async ngOnInit() {
    this.items = await this.dataService.getFeatures("");
  }

  ngAfterViewInit(): void {
    // Ensure proper initialization after view is ready
    this.cdr.detectChanges();
  }



  public onSearch(event: { term: string; items: Feature[] }): void {
    if (event.term !== undefined) {
      this.searchSubject.next(event.term);
    }
  }

  public async updateSuggestionsFrom(event: Event): Promise<void> {
    const input = (event.target as HTMLInputElement)?.value;
    if (input !== undefined && input !== null) {
      this.searchSubject.next(input);
    }
  }

  ngOnDestroy(): void {
    this.searchSubject.complete();
  }
}
